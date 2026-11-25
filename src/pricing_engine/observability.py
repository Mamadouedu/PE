"""Observabilité : logs structurés JSON + request_id par requête HTTP.

Chaque requête génère une ligne JSON avec :
- timestamp ISO-8601 UTC
- request_id (UUID, propagé en header X-Request-ID response, utile pour
  retrouver une requête dans les logs depuis un ticket utilisateur)
- method, path, status_code, duration_ms
- client_ip
- user_email si authentifié

Pensé pour un stack ELK / Datadog / Loki : une ligne = un événement,
tous les champs sont queryables sans parsing regex.

Le niveau log par défaut est INFO. On downgrade à WARN pour les requêtes
sur /healthz et /readyz, qui polluent la timeline avec du bruit
load-balancer (1 ligne par seconde par instance).
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Renvoie le request_id de la requête en cours, ou None hors contexte HTTP."""
    return _request_id_var.get()


class JsonFormatter(logging.Formatter):
    """Formatter qui sérialise chaque record en une ligne JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attache le request_id courant (si on logge depuis un handler)
        rid = _request_id_var.get()
        if rid:
            payload["request_id"] = rid
        # Fields ad-hoc passés via `extra={}`
        for k, v in record.__dict__.items():
            if k in ("args", "msg", "levelname", "levelno", "pathname",
                     "filename", "module", "exc_info", "exc_text", "stack_info",
                     "lineno", "funcName", "created", "msecs", "relativeCreated",
                     "thread", "threadName", "processName", "process", "name",
                     "taskName"):
                continue
            payload[k] = v
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_json_logging(level: str = "INFO") -> None:
    """Remplace les handlers du root logger par un StreamHandler JSON."""
    root = logging.getLogger()
    root.handlers.clear()
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root.addHandler(h)
    root.setLevel(level.upper())


_HEALTH_PATHS = {"/healthz", "/readyz"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware ASGI : génère un request_id, log start + end avec durée.

    La ligne 'end' porte le statut et la durée — c'est souvent celle
    qu'on veut requêter. La ligne 'start' aide à diagnostiquer les
    requêtes qui ne terminent pas (timeout/pendues).
    """

    def __init__(self, app, logger_name: str = "pricinghub.http") -> None:
        super().__init__(app)
        self._log = logging.getLogger(logger_name)

    async def dispatch(self, request: Request, call_next):
        # Reuse le X-Request-ID du client si fourni (trace distribuée),
        # sinon génère un UUID v4.
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = _request_id_var.set(rid)
        start = time.perf_counter()
        status = 500
        try:
            response: Response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        except Exception:
            # L'exception sera gérée par le handler global de FastAPI,
            # mais on garde la trace dans le log avant de la relayer.
            self._log.exception(
                "http_request_error",
                extra={
                    "method": request.method, "path": request.url.path,
                    "client_ip": request.client.host if request.client else None,
                },
            )
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            # Route template (ex. "/catalog/quotes/{quote_id}") et pas
            # le path brut : évite d'exploser la cardinalité des
            # métriques Prometheus avec les UUIDs dans l'URL.
            route = getattr(
                request.scope.get("route"), "path", request.url.path,
            )
            # Les probes K8s sont loguées en DEBUG pour ne pas polluer.
            level = logging.DEBUG if request.url.path in _HEALTH_PATHS else logging.INFO
            self._log.log(
                level, "http_request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "route": route,
                    "status_code": status,
                    "duration_ms": round(duration_ms, 2),
                    "client_ip": request.client.host if request.client else None,
                },
            )
            # Métriques Prometheus (import tardif : évite dépendance
            # dure quand on importe juste observability pour les logs).
            try:
                from .metrics import observe_http_request
                observe_http_request(request.method, route, status, duration_ms)
            except ImportError:
                pass
            _request_id_var.reset(token)
