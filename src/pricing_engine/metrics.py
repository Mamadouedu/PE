"""Métriques Prometheus pour le monitoring en production.

Trois familles de métriques :
1. HTTP générique : compteur par (method, route, status), histogramme
   latence par (method, route). Exposé automatiquement par
   RequestLoggingMiddleware qui route vers `observe_http_request()`.
2. Métier : compteurs d'événements business (login succès/échec,
   quotes créées/submises, décisions direction, dérogations) exposés
   via `record_*()` helpers appelés depuis les endpoints.
3. Système : informations statiques (service, version) via Info.

L'endpoint `/metrics` renvoie le format texte Prometheus standard,
scrapable par un Prometheus server ou un side-car OpenTelemetry.

Important : on utilise le pattern de "route template" (path pattern
FastAPI) et pas le path brut, sinon les UUIDs dans l'URL explosent la
cardinalité (chaque /catalog/quotes/<uuid> serait une série unique,
inutilisable).
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Histogram,
    Info,
    generate_latest,
)


# Buckets d'histogramme en millisecondes, adaptés à un API JSON :
# de 5ms à 10s, logarithmique approximatif. Capture le p50/p95/p99.
_HTTP_BUCKETS_MS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10_000)


# =========================================================================
# HTTP générique
# =========================================================================

http_requests_total = Counter(
    "http_requests_total",
    "Total des requêtes HTTP reçues",
    ["method", "route", "status_code"],
)

http_request_duration_ms = Histogram(
    "http_request_duration_ms",
    "Latence des requêtes HTTP en millisecondes",
    ["method", "route"],
    buckets=_HTTP_BUCKETS_MS,
)

http_requests_in_flight = Counter(
    "http_requests_in_flight_total",
    "Cumul des requêtes HTTP ayant commencé (démarrages cumulés)",
    ["method", "route"],
)


def observe_http_request(method: str, route: str, status_code: int,
                         duration_ms: float) -> None:
    """Appelé par RequestLoggingMiddleware à la fin de chaque requête."""
    http_requests_total.labels(method=method, route=route,
                               status_code=str(status_code)).inc()
    http_request_duration_ms.labels(method=method, route=route).observe(duration_ms)


def record_request_start(method: str, route: str) -> None:
    """Incrément de démarrage, utile pour les requêtes qui ne finissent
    pas (timeout, connexion coupée)."""
    http_requests_in_flight.labels(method=method, route=route).inc()


# =========================================================================
# Métier : login
# =========================================================================

login_attempts_total = Counter(
    "pricinghub_login_attempts_total",
    "Tentatives de login par résultat",
    ["result"],  # success / invalid_password / unknown_user / rate_limited
)


def record_login(result: str) -> None:
    login_attempts_total.labels(result=result).inc()


# =========================================================================
# Métier : quotes
# =========================================================================

quotes_created_total = Counter(
    "pricinghub_quotes_created_total",
    "Quotes créées",
)

quotes_submitted_total = Counter(
    "pricinghub_quotes_submitted_total",
    "Quotes soumises pour validation, par niveau de validation requis",
    ["niveau_validation"],  # 0 (auto) / 1 (pricing) / 2 (direction)
)

quotes_decided_total = Counter(
    "pricinghub_quotes_decided_total",
    "Décisions sur quotes soumises",
    ["decision"],  # approved / rejected
)


def record_quote_created() -> None:
    quotes_created_total.inc()


def record_quote_submitted(niveau_validation: int) -> None:
    quotes_submitted_total.labels(niveau_validation=str(niveau_validation)).inc()


def record_quote_decided(approved: bool) -> None:
    quotes_decided_total.labels(decision="approved" if approved else "rejected").inc()


# =========================================================================
# Système : version + service
# =========================================================================

service_info = Info("pricinghub_service", "Infos statiques du service")


def set_service_info(service: str, version: str) -> None:
    service_info.info({"service": service, "version": version})


# =========================================================================
# Endpoint
# =========================================================================


def build_metrics_router() -> APIRouter:
    router = APIRouter(tags=["metrics"])

    @router.get("/metrics")
    def metrics() -> Response:
        """Expose les métriques au format texte Prometheus standard.

        Scrapable par un Prometheus server avec `scrape_config` pointant
        sur ce path. Content-Type: text/plain;version=0.0.4;charset=utf-8.
        """
        payload = generate_latest(REGISTRY)
        return Response(content=payload, media_type=CONTENT_TYPE_LATEST)

    return router


def get_counter_value(counter, **labels) -> float:
    """Helper tests : lit la valeur courante d'un Counter prometheus.

    Les tests comparent des deltas (valeur après - valeur avant)
    plutôt que des valeurs absolues : plus robuste que de tenter un
    reset global qui échoue sur les counters sans labels (dont
    `_value` vit directement sur l'objet et pas dans `_metrics`)."""
    if labels:
        return counter.labels(**labels)._value.get()
    return counter._value.get()
