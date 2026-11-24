"""Tests de l'audit trail universel."""

from __future__ import annotations

import importlib
import pytest
from fastapi.testclient import TestClient

from pricing_engine.audit import (
    AuditEntry,
    InMemoryAuditStore,
    log_audit,
    set_audit_store,
)


@pytest.fixture
def audit_store():
    store = InMemoryAuditStore()
    set_audit_store(store)
    return store


def test_log_audit_cree_une_entree(audit_store):
    log_audit(
        actor_email="kam1@akiem.com", actor_role="KAM",
        action="CREATE", entity_type="Quote", entity_id="42",
        details={"client": "SNCF"},
    )
    entries = audit_store.list()
    assert len(entries) == 1
    e = entries[0]
    assert e.actor_email == "kam1@akiem.com"
    assert e.action == "CREATE"
    assert e.entity_type == "Quote"
    assert e.details["client"] == "SNCF"


def test_list_filtre_par_action(audit_store):
    log_audit(actor_email="a@x.com", action="CREATE", entity_type="Quote", entity_id="1")
    log_audit(actor_email="a@x.com", action="SUBMIT", entity_type="Quote", entity_id="1")
    log_audit(actor_email="a@x.com", action="CREATE", entity_type="Quote", entity_id="2")

    submits = audit_store.list(action="SUBMIT")
    assert len(submits) == 1
    assert submits[0].entity_id == "1"


def test_list_filtre_par_entity(audit_store):
    log_audit(actor_email="a@x.com", action="CREATE", entity_type="Quote", entity_id="1")
    log_audit(actor_email="a@x.com", action="CREATE", entity_type="FleetAsset", entity_id="L-100")

    quotes = audit_store.list(entity_type="Quote")
    assert len(quotes) == 1
    assert quotes[0].entity_id == "1"


def test_list_renvoie_du_plus_recent_au_plus_ancien(audit_store):
    for i in range(3):
        log_audit(actor_email="a@x.com", action="CREATE", entity_type="Quote", entity_id=str(i))
    entries = audit_store.list()
    # Le plus récent (id=2) en tête
    assert entries[0].entity_id == "2"
    assert entries[-1].entity_id == "0"


# =========================================================================
# Intégration avec l'API
# =========================================================================


@pytest.fixture
def client():
    from pricing_engine import api as api_module
    importlib.reload(api_module)
    return TestClient(api_module.app)


def _login(client, email, mdp):
    r = client.post("/api/v1/auth/login", json={"email": email, "mot_de_passe": mdp})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_api_login_est_audite(client):
    _login(client, "kam1@akiem.com", "kam")
    # Admin peut lire l'audit
    auth_admin = _login(client, "admin@akiem.com", "admin")
    r = client.get("/api/v1/audit?action=LOGIN", headers=auth_admin)
    assert r.status_code == 200
    # Au moins les 2 logins qu'on vient de faire (kam1 + admin)
    emails = {e["actor_email"] for e in r.json()}
    assert "kam1@akiem.com" in emails
    assert "admin@akiem.com" in emails


def test_api_submit_quote_est_audite(client):
    auth_kam = _login(client, "kam1@akiem.com", "kam")

    r = client.post("/api/v1/catalog/quotes",
        json={"client_code": "SNCF", "client_name": "SNCF Fret"},
        headers=auth_kam)
    qid = r.json()["quote_id"]
    client.post(f"/api/v1/catalog/quotes/{qid}/lines",
        json={"technical_variant_code": "E186-DABNL", "country_iso": "DE",
              "duration_months": 24, "age_years": 5, "annual_mileage_km": 150000},
        headers=auth_kam)
    client.post(f"/api/v1/catalog/quotes/{qid}/submit", headers=auth_kam)

    auth_admin = _login(client, "admin@akiem.com", "admin")
    r = client.get(f"/api/v1/audit?action=SUBMIT&entity_type=Quote", headers=auth_admin)
    assert r.status_code == 200
    submits = r.json()
    assert len(submits) >= 1
    s = submits[0]
    assert s["actor_email"] == "kam1@akiem.com"
    assert s["entity_id"] == qid
    assert s["details"]["niveau_validation"] >= 0


def test_api_decide_quote_est_audite(client):
    auth_kam = _login(client, "kam1@akiem.com", "kam")
    auth_dir = _login(client, "direction@akiem.com", "direction")

    r = client.post("/api/v1/catalog/quotes",
        json={"client_code": "ACME", "client_name": "ACME"}, headers=auth_kam)
    qid = r.json()["quote_id"]
    client.post(f"/api/v1/catalog/quotes/{qid}/lines",
        json={"technical_variant_code": "E186-DABNL", "country_iso": "DE",
              "duration_months": 24, "age_years": 5, "annual_mileage_km": 150000},
        headers=auth_kam)
    client.post(f"/api/v1/catalog/quotes/{qid}/submit", headers=auth_kam)

    # Direction approuve
    client.post(f"/api/v1/catalog/quotes/{qid}/decision",
        json={"approved": True, "comment": "OK pour cette fois"},
        headers=auth_dir)

    auth_admin = _login(client, "admin@akiem.com", "admin")
    r = client.get(f"/api/v1/audit?action=APPROVE&entity_id={qid}", headers=auth_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["actor_email"] == "direction@akiem.com"
    assert data[0]["details"]["comment"] == "OK pour cette fois"


def test_kam_ne_peut_pas_lire_l_audit(client):
    auth = _login(client, "kam1@akiem.com", "kam")
    r = client.get("/api/v1/audit", headers=auth)
    assert r.status_code == 403
