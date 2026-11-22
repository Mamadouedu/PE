"""Tests de l'authentification + isolation des accès par rôle."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_strict(monkeypatch):
    """TestClient avec REQUIRE_AUTH=1 pour vérifier l'isolation."""
    monkeypatch.setenv("REQUIRE_AUTH", "1")
    # reimport pour prendre en compte la var
    import importlib
    from pricing_engine import api as api_module
    importlib.reload(api_module)
    client = TestClient(api_module.app)
    yield client


@pytest.fixture
def client_tolerant():
    from pricing_engine.api import app
    return TestClient(app)


def _login(client, email, mot_de_passe) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "mot_de_passe": mot_de_passe})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_hachage_et_verification_mot_de_passe():
    from pricing_engine.users import hacher_mot_de_passe, verifier_mot_de_passe
    h = hacher_mot_de_passe("secret")
    assert verifier_mot_de_passe("secret", h)
    assert not verifier_mot_de_passe("mauvais", h)
    # Deux hashes du même mot de passe sont différents (salt aléatoire)
    assert hacher_mot_de_passe("secret") != h


def test_login_mauvais_mot_de_passe(client_strict):
    r = client_strict.post("/api/v1/auth/login", json={"email": "admin@akiem.com", "mot_de_passe": "faux"})
    assert r.status_code == 401


def test_login_utilisateur_inconnu(client_strict):
    r = client_strict.post("/api/v1/auth/login", json={"email": "ghost@akiem.com", "mot_de_passe": "x"})
    assert r.status_code == 401


def test_me_sans_auth_refuse_en_mode_strict(client_strict):
    r = client_strict.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_login_ouvre_une_session_et_me_marche(client_strict):
    token = _login(client_strict, "admin@akiem.com", "admin")
    r = client_strict.get("/api/v1/auth/me", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "admin@akiem.com"
    assert data["role"] == "ADMIN"
    assert "gerer_utilisateurs" in data["permissions"]


def test_logout_invalide_le_token(client_strict):
    token = _login(client_strict, "admin@akiem.com", "admin")
    client_strict.post("/api/v1/auth/logout", headers=_auth(token))
    r = client_strict.get("/api/v1/auth/me", headers=_auth(token))
    assert r.status_code == 401


def test_kam_voit_seulement_ses_derogations(client_strict, publier_referentiel_min):
    tok1 = _login(client_strict, "kam1@akiem.com", "kam")
    tok2 = _login(client_strict, "kam2@akiem.com", "kam")
    tok_head = _login(client_strict, "head@akiem.com", "pricing")

    # KAM1 et KAM2 créent chacun une dérogation
    config = {
        "client_code": "CLIENTOK", "serie_code": "VECTRON", "km_annuel": 120000,
        "duree_mois": 24, "quantite": 1, "date_debut": "2026-01-01",
        "age_debut_ans": 5, "km_cumules_debut": 600000,
        "prix_negocies": {"DL": 15000},
    }
    for tok in (tok1, tok2):
        r = client_strict.post(
            "/api/v1/derogations",
            json={"configuration": config, "justification": "demo"},
            headers=_auth(tok),
        )
        assert r.status_code == 200, r.text

    # KAM1 ne voit que la sienne
    r1 = client_strict.get("/api/v1/derogations", headers=_auth(tok1))
    assert r1.status_code == 200
    mes1 = r1.json()
    assert len(mes1) == 1
    assert mes1[0]["demandeur"].lower() == "kam1@akiem.com"

    # KAM2 ne voit que la sienne
    r2 = client_strict.get("/api/v1/derogations", headers=_auth(tok2))
    mes2 = r2.json()
    assert len(mes2) == 1
    assert mes2[0]["demandeur"].lower() == "kam2@akiem.com"

    # Head of Pricing voit les deux
    r_head = client_strict.get("/api/v1/derogations", headers=_auth(tok_head))
    assert len(r_head.json()) >= 2


def test_kam_voit_seulement_ses_offres_pdf(client_strict, publier_referentiel_min):
    tok1 = _login(client_strict, "kam1@akiem.com", "kam")
    tok2 = _login(client_strict, "kam2@akiem.com", "kam")
    tok_admin = _login(client_strict, "admin@akiem.com", "admin")

    config = {
        "client_code": "CLIENTOK", "serie_code": "VECTRON", "km_annuel": 120000,
        "duree_mois": 24, "quantite": 1, "date_debut": "2026-01-01",
        "age_debut_ans": 5, "km_cumules_debut": 600000,
    }
    for tok in (tok1, tok1, tok2):
        r = client_strict.post("/api/v1/offres/pdf", json=config, headers=_auth(tok))
        assert r.status_code == 200, r.text

    r1 = client_strict.get("/api/v1/offres", headers=_auth(tok1))
    offres1 = r1.json()
    assert len(offres1) == 2
    assert all(o["utilisateur"].lower() == "kam1@akiem.com" for o in offres1)

    r2 = client_strict.get("/api/v1/offres", headers=_auth(tok2))
    assert len(r2.json()) == 1

    r_admin = client_strict.get("/api/v1/offres", headers=_auth(tok_admin))
    assert len(r_admin.json()) == 3


def test_seul_un_role_avec_permission_gere_les_utilisateurs(client_strict):
    tok_kam = _login(client_strict, "kam1@akiem.com", "kam")
    tok_head = _login(client_strict, "head@akiem.com", "pricing")
    tok_admin = _login(client_strict, "admin@akiem.com", "admin")

    r_kam = client_strict.get("/api/v1/utilisateurs", headers=_auth(tok_kam))
    assert r_kam.status_code == 403
    r_head = client_strict.get("/api/v1/utilisateurs", headers=_auth(tok_head))
    assert r_head.status_code == 403  # Pricing n'a pas la permission
    r_admin = client_strict.get("/api/v1/utilisateurs", headers=_auth(tok_admin))
    assert r_admin.status_code == 200


def test_changer_mot_de_passe_revoque_les_sessions(client_strict):
    tok = _login(client_strict, "kam1@akiem.com", "kam")
    r = client_strict.post(
        "/api/v1/auth/change-password",
        json={"ancien_mot_de_passe": "kam", "nouveau_mot_de_passe": "nouveau123"},
        headers=_auth(tok),
    )
    assert r.status_code == 200

    # L'ancien token est invalide
    r2 = client_strict.get("/api/v1/auth/me", headers=_auth(tok))
    assert r2.status_code == 401

    # Avec le nouveau mot de passe ça marche
    tok_bis = _login(client_strict, "kam1@akiem.com", "nouveau123")
    r3 = client_strict.get("/api/v1/auth/me", headers=_auth(tok_bis))
    assert r3.status_code == 200


# Helper : publie un référentiel minimal pour que les endpoints prix/offres marchent
@pytest.fixture
def publier_referentiel_min(client_strict):
    tok_admin = _login(client_strict, "admin@akiem.com", "admin")
    headers = {**_auth(tok_admin), "X-Utilisateur": "admin@akiem.com"}

    r = client_strict.post("/api/v1/referentiel/brouillons", headers=headers)
    assert r.status_code == 200
    numero = r.json()["numero"]

    def put(path, payload):
        client_strict.put(path, json=payload, headers=headers)

    put(f"/api/v1/referentiel/brouillons/{numero}/series/VECTRON", {"serie": {
        "code": "VECTRON", "valeur_neuve": 2_000_000, "duree_vie_ans": 30,
        "vr_fin_vie_taux": 0.10, "km_reference_annuel": 120_000,
        "cout_hm_8_ans": 150_000, "cout_hm_16_ans": 200_000,
        "om_fixe": 6_000, "om_variable_eur_par_km": 0.05, "taux_assurance_annuel": 0.03,
    }})
    tr = {"km_min": 80_000, "km_max": 200_000, "coefficient_dl": 1.0, "coefficient_hm": 1.0, "coefficient_om": 1.0}
    put(f"/api/v1/referentiel/brouillons/{numero}/tranches-km", [tr])
    put(f"/api/v1/referentiel/brouillons/{numero}/grille-dry-lease", [{
        "serie_code": "VECTRON",
        "tranche_duree": {"duree_min_mois": 0, "duree_max_mois": None},
        "loyer_mensuel": 20_000,
    }])
    put(f"/api/v1/referentiel/brouillons/{numero}/budget-plan", [{
        "serie_code": "VECTRON", "tranche_km": tr, "bp_hm": 2000, "bp_om": 1500, "exercice": "2026"
    }])
    put(f"/api/v1/referentiel/brouillons/{numero}/clients/CLIENTOK", {
        "code": "CLIENTOK", "nom": "Client", "rating": 5, "paiement_avance": True,
    })
    put(f"/api/v1/referentiel/brouillons/{numero}/delegations", [
        {"niveau": 1, "nom": "M", "email": "manager@akiem.com"},
        {"niveau": 2, "nom": "H", "email": "head@akiem.com"},
    ])
    client_strict.post(f"/api/v1/referentiel/brouillons/{numero}/publier", headers=headers)
    yield numero
