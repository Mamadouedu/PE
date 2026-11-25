# Multi-stage build pour l'API PricingHub.
#
# Stage 1 (builder) : installe les dépendances dans un venv isolé.
# Compile argon2-cffi, psycopg[binary], etc. une seule fois, puis
# copie seulement le venv dans l'image finale.
#
# Stage 2 (runtime) : image mince sans toolchain, exécute gunicorn
# avec workers uvicorn. User non-root.
#
# Usage :
#   docker build -t pricinghub-api .
#   docker run -p 8000:8000 \
#     -e DATABASE_URL=postgresql+psycopg://... \
#     -e CATALOG_DATABASE_URL=postgresql+psycopg://... \
#     -e REDIS_URL=redis://... \
#     -e LOG_FORMAT=json \
#     pricinghub-api

ARG PYTHON_VERSION=3.13

# =========================================================================
# Stage 1 : builder
# =========================================================================
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Toolchain pour compiler argon2-cffi et psycopg quand les wheels
# binaires ne couvrent pas la plateforme ciblée.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Venv dédié : plus simple à copier dans le runtime que --user.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copie d'abord les manifests pour tirer parti du cache Docker : tant
# que pyproject.toml ne bouge pas, pip install est en cache.
COPY pyproject.toml ./
COPY src ./src

RUN pip install --upgrade pip setuptools wheel \
 && pip install -e ".[dev]" \
 && pip install gunicorn


# =========================================================================
# Stage 2 : runtime
# =========================================================================
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# libpq pour psycopg en runtime. Pas de toolchain de build.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# User non-root : limite les dégâts si le process est compromis.
RUN groupadd --system app && useradd --system --gid app --home /app app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/src /app/src
COPY pyproject.toml /app/
COPY alembic.ini /app/
COPY migrations /app/migrations

WORKDIR /app
RUN chown -R app:app /app
USER app

EXPOSE 8000

# Healthcheck Docker : utile en standalone (docker run) ; K8s utilise
# /readyz via son propre probe, pas celui du Dockerfile.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

# Gunicorn + workers uvicorn : production-grade, graceful restart,
# nombre de workers adaptable via GUNICORN_WORKERS (défaut 2, bon
# pour 1 CPU alloué avec I/O-bound).
ENV GUNICORN_WORKERS=2 \
    GUNICORN_TIMEOUT=60 \
    LOG_FORMAT=json

CMD ["sh", "-c", "exec gunicorn pricing_engine.api:app \
    --workers ${GUNICORN_WORKERS} \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout ${GUNICORN_TIMEOUT} \
    --access-logfile - \
    --error-logfile -"]
