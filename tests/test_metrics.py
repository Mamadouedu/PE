"""Tests des métriques Prometheus.

On compare des deltas (valeur après - valeur avant l'action) plutôt
que des absolus : pas de reset global robuste pour un Counter sans
labels (son `_value` vit directement sur l'objet, pas dans `_metrics`)
et les assertions deltas sont indépendantes de l'ordre des tests.
"""

from __future__ import annotations

import importlib
import os

import pytest
from fastapi.testclient import TestClient

from pricing_engine.metrics import (
    get_counter_value,
    http_requests_total,
    login_attempts_total,
    quotes_created_total,
    quotes_decided_total,
    quotes_submitted_total,
)


@pytest.fixture
def client():
    for v in ("CATALOG_DATABASE_URL", "REDIS_URL"):
        os.environ.pop(v, None)
    from pricing_engine import api as api_module
    importlib.reload(api_module)
    from pricing_engine.rate_limit import InMemoryRateLimiter
    api_module._rate_limiter = InMemoryRateLimiter()
    return TestClient(api_module.app), api_module


# =========================================================================
# Endpoint /metrics
# =========================================================================


def test_metrics_endpoint_200_format_text(client):
    c, _ = client
    r = c.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    assert "# HELP" in body
    assert "# TYPE" in body


def test_metrics_contient_les_familles_attendues(client):
    c, _ = client
    c.get("/healthz")

    body = c.get("/metrics").text
    assert "http_requests_total" in body
    assert "http_request_duration_ms" in body
    assert "pricinghub_login_attempts_total" in body
    assert "pricinghub_quotes_created_total" in body
    assert "pricinghub_quotes_submitted_total" in body
    assert "pricinghub_quotes_decided_total" in body
    assert "pricinghub_service_info" in body


# =========================================================================
# Compteurs HTTP incrémentés par le middleware
# =========================================================================


def test_http_requests_total_incremente(client):
    c, _ = client
    avant = get_counter_value(http_requests_total,
                              method="GET", route="/healthz", status_code="200")
    for _ in range(3):
        c.get("/healthz")
    apres = get_counter_value(http_requests_total,
                              method="GET", route="/healthz", status_code="200")
    assert apres - avant == 3


def test_http_request_duration_histogramme(client):
    c, _ = client
    c.get("/healthz")

    body = c.get("/metrics").text
    assert "http_request_duration_ms_bucket" in body
    assert "http_request_duration_ms_sum" in body
    assert "http_request_duration_ms_count" in body


def test_route_template_pas_path_brut(client):
    """Pour /catalog/quotes/{id}, le label doit être la route template
    (évite l'explosion de cardinalité avec des UUIDs dans les labels)."""
    c, _ = client
    auth = {"Authorization": "Bearer " + c.post(
        "/api/v1/auth/login",
        json={"email": "kam1@akiem.com", "mot_de_passe": "kam"}
    ).json()["token"]}
    qid = c.post("/api/v1/catalog/quotes",
                 json={"client_code": "X", "client_name": "X"},
                 headers=auth).json()["quote_id"]
    c.get(f"/api/v1/catalog/quotes/{qid}", headers=auth)

    body = c.get("/metrics").text
    assert qid not in body
    assert "{quote_id}" in body


# =========================================================================
# Compteurs métier login
# =========================================================================


def test_login_success_incremente_counter(client):
    c, _ = client
    avant = get_counter_value(login_attempts_total, result="success")
    r = c.post("/api/v1/auth/login",
               json={"email": "kam1@akiem.com", "mot_de_passe": "kam"})
    assert r.status_code == 200
    assert get_counter_value(login_attempts_total, result="success") - avant == 1


def test_login_invalid_password_incremente_counter(client):
    c, _ = client
    avant = get_counter_value(login_attempts_total, result="invalid_password")
    c.post("/api/v1/auth/login",
           json={"email": "kam1@akiem.com", "mot_de_passe": "WRONG"})
    assert get_counter_value(login_attempts_total, result="invalid_password") - avant == 1


def test_login_unknown_user_incremente_counter(client):
    c, _ = client
    avant = get_counter_value(login_attempts_total, result="unknown_user")
    c.post("/api/v1/auth/login",
           json={"email": "nobody@akiem.com", "mot_de_passe": "x"})
    assert get_counter_value(login_attempts_total, result="unknown_user") - avant == 1


def test_login_rate_limited_incremente_counter(client):
    c, _ = client
    from pricing_engine.rate_limit import MAX_ECHECS_EMAIL
    avant = get_counter_value(login_attempts_total, result="rate_limited")
    for _ in range(MAX_ECHECS_EMAIL):
        c.post("/api/v1/auth/login",
               json={"email": "kam1@akiem.com", "mot_de_passe": "WRONG"})
    c.post("/api/v1/auth/login",
           json={"email": "kam1@akiem.com", "mot_de_passe": "WRONG"})
    assert get_counter_value(login_attempts_total, result="rate_limited") - avant == 1


# =========================================================================
# Compteurs métier quotes
# =========================================================================


def test_quote_created_incremente_counter(client):
    c, _ = client
    avant = get_counter_value(quotes_created_total)
    auth = {"Authorization": "Bearer " + c.post(
        "/api/v1/auth/login",
        json={"email": "kam1@akiem.com", "mot_de_passe": "kam"}
    ).json()["token"]}
    c.post("/api/v1/catalog/quotes",
           json={"client_code": "X", "client_name": "X"}, headers=auth)
    c.post("/api/v1/catalog/quotes",
           json={"client_code": "Y", "client_name": "Y"}, headers=auth)

    assert get_counter_value(quotes_created_total) - avant == 2


def test_quote_submitted_incremente_counter_avec_niveau(client):
    c, _ = client
    auth = {"Authorization": "Bearer " + c.post(
        "/api/v1/auth/login",
        json={"email": "kam1@akiem.com", "mot_de_passe": "kam"}
    ).json()["token"]}
    qid = c.post("/api/v1/catalog/quotes",
                 json={"client_code": "X", "client_name": "X"},
                 headers=auth).json()["quote_id"]
    c.post(f"/api/v1/catalog/quotes/{qid}/lines",
           json={"technical_variant_code": "E186-DABNL", "country_iso": "DE",
                 "duration_months": 24, "age_years": 5, "annual_mileage_km": 150_000},
           headers=auth)

    # Capture avant submit
    r = c.post(f"/api/v1/catalog/quotes/{qid}/submit", headers=auth)
    niveau = r.json()["niveau_validation"]
    # Après submit, le counter du niveau pertinent est à ≥ 1
    assert get_counter_value(quotes_submitted_total,
                             niveau_validation=str(niveau)) >= 1


def test_quote_decided_incremente_counter_approve(client):
    c, _ = client
    auth_kam = {"Authorization": "Bearer " + c.post(
        "/api/v1/auth/login",
        json={"email": "kam1@akiem.com", "mot_de_passe": "kam"}
    ).json()["token"]}
    auth_dir = {"Authorization": "Bearer " + c.post(
        "/api/v1/auth/login",
        json={"email": "direction@akiem.com", "mot_de_passe": "direction"}
    ).json()["token"]}

    avant = get_counter_value(quotes_decided_total, decision="approved")
    qid = c.post("/api/v1/catalog/quotes",
                 json={"client_code": "A", "client_name": "A"},
                 headers=auth_kam).json()["quote_id"]
    c.post(f"/api/v1/catalog/quotes/{qid}/lines",
           json={"technical_variant_code": "E186-DABNL", "country_iso": "DE",
                 "duration_months": 24, "age_years": 5, "annual_mileage_km": 150_000},
           headers=auth_kam)
    c.post(f"/api/v1/catalog/quotes/{qid}/submit", headers=auth_kam)
    c.post(f"/api/v1/catalog/quotes/{qid}/decision",
           json={"approved": True, "comment": ""}, headers=auth_dir)

    assert get_counter_value(quotes_decided_total, decision="approved") - avant == 1


# =========================================================================
# Service info
# =========================================================================


def test_service_info_present(client):
    c, _ = client
    body = c.get("/metrics").text
    assert 'pricinghub_service_info' in body
    assert 'service="pricinghub-api"' in body
    assert 'version="0.1.0"' in body
