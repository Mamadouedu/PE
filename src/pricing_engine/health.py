"""Endpoints de santé pour un déploiement Kubernetes / load-balancer.

Deux conventions séparées :
- `/healthz` (liveness) : le process répond. Si ça échoue, redémarre
  le conteneur. On ne vérifie que des trucs internes, pas les
  dépendances externes : sinon une panne Redis fait redémarrer en
  boucle et masque le vrai problème.
- `/readyz` (readiness) : le process est prêt à recevoir du trafic.
  Vérifie les dépendances critiques (DB + Redis). Si ça échoue, le
  load-balancer sort cette instance du pool jusqu'à la réparation.
  Pas de restart, juste pas de trafic.

Retourne du JSON structuré : chaque check est son propre champ avec
status + éventuellement un message d'erreur court. 200 si tout est
healthy, 503 sinon.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Response


@dataclass
class CheckResult:
    name: str
    healthy: bool
    latency_ms: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": "healthy" if self.healthy else "unhealthy",
            "latency_ms": round(self.latency_ms, 2),
        }
        if self.error:
            d["error"] = self.error
        return d


def _time_check(name: str, fn) -> CheckResult:
    """Exécute fn(), chronomètre, capture toute exception."""
    start = time.perf_counter()
    try:
        fn()
        return CheckResult(name=name, healthy=True,
                           latency_ms=(time.perf_counter() - start) * 1000)
    except Exception as e:
        return CheckResult(name=name, healthy=False,
                           latency_ms=(time.perf_counter() - start) * 1000,
                           error=str(e)[:200])


def check_database(session_factory) -> CheckResult:
    """Ping DB via SELECT 1. Un timeout réseau ou une DB down échoue ici."""
    def _probe():
        from sqlalchemy import text
        with session_factory() as s:
            s.execute(text("SELECT 1")).scalar()
    return _time_check("database", _probe)


def check_redis(redis_client) -> CheckResult:
    def _probe():
        redis_client.ping()
    return _time_check("redis", _probe)


def build_health_router(
    *, get_db_session_factory=None, get_redis_client=None,
    service_name: str = "pricinghub-api", version: str = "0.1.0",
) -> APIRouter:
    """Construit le router avec les deux endpoints.

    Les deux dépendances sont des callables (ou None) : on ne les
    appelle qu'au moment du check pour que la bascule dynamique
    (reload de l'API) soit prise en compte.
    """

    router = APIRouter(tags=["health"])

    @router.get("/healthz", status_code=200)
    def liveness() -> dict[str, Any]:
        """Liveness : le process répond, c'est tout. Pas de dépendances."""
        return {
            "status": "healthy",
            "service": service_name,
            "version": version,
        }

    @router.get("/readyz")
    def readiness(response: Response) -> dict[str, Any]:
        """Readiness : vérifie que les dépendances critiques répondent."""
        checks: dict[str, Any] = {}
        all_healthy = True

        if get_db_session_factory is not None:
            sf = get_db_session_factory()
            if sf is not None:
                res = check_database(sf)
                checks["database"] = res.to_dict()
                all_healthy = all_healthy and res.healthy

        if get_redis_client is not None:
            rc = get_redis_client()
            if rc is not None:
                res = check_redis(rc)
                checks["redis"] = res.to_dict()
                all_healthy = all_healthy and res.healthy

        response.status_code = 200 if all_healthy else 503
        return {
            "status": "ready" if all_healthy else "not_ready",
            "service": service_name,
            "version": version,
            "checks": checks,
        }

    return router
