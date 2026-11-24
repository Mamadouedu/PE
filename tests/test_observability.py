"""Tests de l'observabilité : logs JSON + request_id."""

from __future__ import annotations

import importlib
import io
import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pricing_engine.observability import (
    JsonFormatter,
    RequestLoggingMiddleware,
    _request_id_var,
    configure_json_logging,
    get_request_id,
)


# =========================================================================
# JsonFormatter
# =========================================================================


def test_json_formatter_rend_une_ligne_json_valide():
    rec = logging.LogRecord(
        name="test", level=logging.INFO, pathname="t.py", lineno=1,
        msg="hello", args=(), exc_info=None,
    )
    out = JsonFormatter().format(rec)
    data = json.loads(out)
    assert data["level"] == "INFO"
    assert data["logger"] == "test"
    assert data["message"] == "hello"
    assert "ts" in data


def test_json_formatter_inclut_extra_fields():
    rec = logging.LogRecord(
        name="t", level=logging.INFO, pathname="t.py", lineno=1,
        msg="m", args=(), exc_info=None,
    )
    rec.method = "POST"
    rec.status_code = 200
    data = json.loads(JsonFormatter().format(rec))
    assert data["method"] == "POST"
    assert data["status_code"] == 200


def test_json_formatter_inclut_request_id_courant():
    _request_id_var.set("abc-123")
    rec = logging.LogRecord(
        name="t", level=logging.INFO, pathname="t.py", lineno=1,
        msg="m", args=(), exc_info=None,
    )
    data = json.loads(JsonFormatter().format(rec))
    assert data["request_id"] == "abc-123"
    _request_id_var.set(None)


def test_json_formatter_exception_formatee():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        rec = logging.LogRecord(
            name="t", level=logging.ERROR, pathname="t.py", lineno=1,
            msg="oops", args=(), exc_info=sys.exc_info(),
        )
    data = json.loads(JsonFormatter().format(rec))
    assert "exception" in data
    assert "ValueError" in data["exception"]


# =========================================================================
# Middleware : request_id généré, retourné en header, propagé en logs
# =========================================================================


@pytest.fixture
def app_with_mw():
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ping")
    def ping():
        return {"request_id": get_request_id(), "ok": True}

    @app.get("/boom")
    def boom():
        raise RuntimeError("explose")

    return app


def test_middleware_genere_request_id(app_with_mw):
    c = TestClient(app_with_mw, raise_server_exceptions=False)
    r = c.get("/ping")
    assert r.status_code == 200
    rid = r.headers.get("X-Request-ID")
    assert rid
    # Le handler a vu le même request_id
    assert r.json()["request_id"] == rid


def test_middleware_respecte_le_request_id_amont(app_with_mw):
    """Trace distribuée : si le client envoie son X-Request-ID, on le
    reprend pour corréler les logs dans toute la chaîne."""
    c = TestClient(app_with_mw, raise_server_exceptions=False)
    r = c.get("/ping", headers={"X-Request-ID": "trace-upstream-42"})
    assert r.headers["X-Request-ID"] == "trace-upstream-42"
    assert r.json()["request_id"] == "trace-upstream-42"


def test_middleware_request_ids_differents_par_requete(app_with_mw):
    c = TestClient(app_with_mw, raise_server_exceptions=False)
    r1 = c.get("/ping")
    r2 = c.get("/ping")
    assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]


def test_middleware_log_contient_les_champs_clefs(app_with_mw, caplog):
    c = TestClient(app_with_mw, raise_server_exceptions=False)
    with caplog.at_level(logging.INFO, logger="pricinghub.http"):
        c.get("/ping")
    recs = [r for r in caplog.records if r.message == "http_request"]
    assert len(recs) == 1
    rec = recs[0]
    assert rec.method == "GET"
    assert rec.path == "/ping"
    assert rec.status_code == 200
    assert rec.duration_ms >= 0


def test_middleware_log_health_en_debug_pas_info(app_with_mw, caplog):
    """Les probes K8s n'ont pas à polluer la timeline INFO."""
    @app_with_mw.get("/healthz")
    def _h():
        return {}

    c = TestClient(app_with_mw, raise_server_exceptions=False)
    with caplog.at_level(logging.INFO, logger="pricinghub.http"):
        c.get("/healthz")
    recs = [r for r in caplog.records if r.message == "http_request"]
    # Au niveau INFO, le probe doit être filtré
    assert len(recs) == 0


def test_middleware_log_exception_sans_masquer(app_with_mw, caplog):
    c = TestClient(app_with_mw, raise_server_exceptions=False)
    with caplog.at_level(logging.INFO, logger="pricinghub.http"):
        r = c.get("/boom")
    assert r.status_code == 500
    # On a bien une entrée d'erreur + une entrée finale
    err_logs = [r for r in caplog.records if r.message == "http_request_error"]
    assert len(err_logs) == 1


# =========================================================================
# configure_json_logging : bascule globale
# =========================================================================


def test_configure_json_logging_installe_un_handler_json(caplog):
    # Baseline
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        configure_json_logging(level="DEBUG")
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
        assert root.level == logging.DEBUG
    finally:
        # Restaure les handlers d'origine pour ne pas polluer la suite
        root.handlers.clear()
        for h in before:
            root.addHandler(h)


# =========================================================================
# Intégration API : request_id visible côté client
# =========================================================================


@pytest.fixture
def client_api():
    import os
    os.environ.pop("CATALOG_DATABASE_URL", None)
    os.environ.pop("REDIS_URL", None)
    from pricing_engine import api as api_module
    importlib.reload(api_module)
    return TestClient(api_module.app)


def test_api_expose_request_id(client_api):
    r = client_api.get("/healthz")
    assert r.status_code == 200
    assert "X-Request-ID" in r.headers
