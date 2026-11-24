"""Tests des endpoints de santé (liveness + readiness)."""

from __future__ import annotations

import importlib
import os

import fakeredis
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    # Reload sans URL de DB ni Redis : checks vides, tout healthy
    for v in ("CATALOG_DATABASE_URL", "REDIS_URL"):
        os.environ.pop(v, None)
    from pricing_engine import api as api_module
    importlib.reload(api_module)
    return TestClient(api_module.app)


# =========================================================================
# /healthz — liveness
# =========================================================================


def test_healthz_toujours_200(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["service"] == "pricinghub-api"
    assert "version" in data


def test_healthz_ne_depend_pas_des_dependances():
    """Liveness ne doit pas sonder les deps : si Redis/DB tombent, le
    pod ne doit PAS être redémarré, il doit juste être retiré du pool
    de trafic (c'est le job de readyz)."""
    # On monte une app avec un fake broken redis/db ; healthz doit
    # quand même retourner 200
    from pricing_engine.health import build_health_router
    from fastapi import FastAPI

    def broken_db():
        raise RuntimeError("DB down")

    def broken_redis():
        class R:
            def ping(self): raise RuntimeError("Redis down")
        return R()

    app = FastAPI()
    app.include_router(build_health_router(
        get_db_session_factory=broken_db,
        get_redis_client=broken_redis,
    ))
    c = TestClient(app)
    r = c.get("/healthz")
    assert r.status_code == 200


# =========================================================================
# /readyz — readiness
# =========================================================================


def test_readyz_200_sans_dependances(client):
    """Mode in-memory pur : pas de DB, pas de Redis, tout est ready."""
    r = client.get("/readyz")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ready"
    assert data["checks"] == {}


def test_readyz_200_avec_db_sqlite(tmp_path, monkeypatch):
    """SQLite file : le check doit répondre healthy."""
    monkeypatch.setenv("CATALOG_DATABASE_URL", f"sqlite:///{tmp_path}/ready.db")
    from pricing_engine import api as api_module
    importlib.reload(api_module)
    c = TestClient(api_module.app)
    r = c.get("/readyz")
    assert r.status_code == 200
    data = r.json()
    assert data["checks"]["database"]["status"] == "healthy"
    assert data["checks"]["database"]["latency_ms"] >= 0


def test_readyz_503_si_db_down(monkeypatch):
    """Si l'URL pointe sur une DB inaccessible, 503."""
    monkeypatch.setenv(
        "CATALOG_DATABASE_URL",
        "postgresql+psycopg://nope:nope@localhost:9999/nope",
    )
    # Reload va échouer au seed → on construit l'app manuellement
    from pricing_engine.health import build_health_router
    from pricing_engine.catalog.sql_store import make_catalog_session_factory
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(build_health_router(
        get_db_session_factory=lambda: make_catalog_session_factory(
            os.environ["CATALOG_DATABASE_URL"]),
    ))
    c = TestClient(app)
    r = c.get("/readyz")
    assert r.status_code == 503
    data = r.json()
    assert data["status"] == "not_ready"
    assert data["checks"]["database"]["status"] == "unhealthy"
    assert "error" in data["checks"]["database"]


def test_readyz_avec_redis_fake():
    """Redis up → ready."""
    from pricing_engine.health import build_health_router
    from fastapi import FastAPI

    fake = fakeredis.FakeRedis()
    app = FastAPI()
    app.include_router(build_health_router(
        get_redis_client=lambda: fake,
    ))
    c = TestClient(app)
    r = c.get("/readyz")
    assert r.status_code == 200
    assert r.json()["checks"]["redis"]["status"] == "healthy"


def test_readyz_503_si_redis_down():
    """Redis qui lève → 503."""
    from pricing_engine.health import build_health_router
    from fastapi import FastAPI

    class BrokenRedis:
        def ping(self):
            raise ConnectionError("Redis unreachable")

    app = FastAPI()
    app.include_router(build_health_router(
        get_redis_client=lambda: BrokenRedis(),
    ))
    c = TestClient(app)
    r = c.get("/readyz")
    assert r.status_code == 503
    assert r.json()["checks"]["redis"]["status"] == "unhealthy"


def test_readyz_combine_db_et_redis():
    """Si l'un des deux est KO, 503 global."""
    from pricing_engine.health import build_health_router
    from fastapi import FastAPI
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    good_db_sf = sessionmaker(bind=create_engine("sqlite:///:memory:"))
    bad_redis = type("R", (), {"ping": lambda self: (_ for _ in ()).throw(RuntimeError("x"))})()

    app = FastAPI()
    app.include_router(build_health_router(
        get_db_session_factory=lambda: good_db_sf,
        get_redis_client=lambda: bad_redis,
    ))
    c = TestClient(app)
    r = c.get("/readyz")
    assert r.status_code == 503
    checks = r.json()["checks"]
    assert checks["database"]["status"] == "healthy"
    assert checks["redis"]["status"] == "unhealthy"
