"""Tests d'intégration de l'API (M2-06)."""

import pytest
from fastapi.testclient import TestClient

import pricing_engine.api as api_module
from pricing_engine.derogation import InMemoryDerogationStore
from pricing_engine.referentiel import Referentiel

HEADERS = {"X-Utilisateur": "pricing@akiem.com"}


@pytest.fixture(autouse=True)
def referentiel_propre():
    api_module._referentiel = Referentiel()
    api_module._derogations = InMemoryDerogationStore()
    yield


@pytest.fixture
def client():
    return TestClient(api_module.app)


def _publier_referentiel_complet(client: TestClient) -> int:
    numero = client.post("/api/v1/referentiel/brouillons").json()["numero"]

    serie = {
        "code": "VECTRON",
        "valeur_neuve": 2_000_000,
        "duree_vie_ans": 30,
        "vr_fin_vie_taux": 0.10,
        "km_reference_annuel": 120_000,
        "cout_hm_8_ans": 150_000,
        "cout_hm_16_ans": 200_000,
        "om_fixe": 6_000,
        "om_variable_eur_par_km": 0.05,
        "taux_assurance_annuel": 0.03,
    }
    r = client.put(
        f"/api/v1/referentiel/brouillons/{numero}/series/VECTRON",
        json={"serie": serie, "raison": "Création série VECTRON"},
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text

    tranche_a = {"km_min": 80_000, "km_max": 149_999, "coefficient_dl": 1.0, "coefficient_hm": 1.0, "coefficient_om": 1.0}
    r = client.put(
        f"/api/v1/referentiel/brouillons/{numero}/tranches-km", json=[tranche_a], headers=HEADERS
    )
    assert r.status_code == 200, r.text

    grille = [
        {
            "serie_code": "VECTRON",
            "tranche_duree": {"duree_min_mois": 0, "duree_max_mois": None},
            "loyer_mensuel": 20_000,
        }
    ]
    r = client.put(
        f"/api/v1/referentiel/brouillons/{numero}/grille-dry-lease", json=grille, headers=HEADERS
    )
    assert r.status_code == 200, r.text

    bp = [{"serie_code": "VECTRON", "tranche_km": tranche_a, "bp_hm": 2_000, "bp_om": 1_500, "exercice": "2026"}]
    r = client.put(
        f"/api/v1/referentiel/brouillons/{numero}/budget-plan", json=bp, headers=HEADERS
    )
    assert r.status_code == 200, r.text

    client_pricing = {
        "code": "CLIENTOK",
        "nom": "Client standard",
        "rating": 5,
        "segment": "",
        "cash_deposit": 0,
        "paiement_avance": True,
    }
    r = client.put(
        f"/api/v1/referentiel/brouillons/{numero}/clients/CLIENTOK",
        json=client_pricing,
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text

    delegations = [
        {"niveau": 1, "nom": "Manager", "email": "manager@akiem.com", "suppleant_email": None},
        {"niveau": 2, "nom": "Head of Pricing", "email": "head@akiem.com", "suppleant_email": None},
        {"niveau": 3, "nom": "Direction", "email": "direction@akiem.com", "suppleant_email": None},
    ]
    r = client.put(
        f"/api/v1/referentiel/brouillons/{numero}/delegations", json=delegations, headers=HEADERS
    )
    assert r.status_code == 200, r.text

    return numero


def test_cycle_de_vie_complet_du_referentiel_et_chiffrage(client: TestClient):
    numero = _publier_referentiel_complet(client)

    r = client.get(f"/api/v1/referentiel/brouillons/{numero}/controles-qualite")
    assert r.status_code == 200
    assert not any(a["bloquante"] for a in r.json())

    r = client.post(f"/api/v1/referentiel/brouillons/{numero}/publier", headers=HEADERS)
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "publie"

    r = client.get("/api/v1/referentiel/publiee")
    assert r.status_code == 200
    assert r.json()["numero"] == numero

    config = {
        "client_code": "CLIENTOK",
        "serie_code": "VECTRON",
        "km_annuel": 120_000,
        "duree_mois": 24,
        "quantite": 1,
        "date_debut": "2026-01-01",
        "age_debut_ans": 5,
        "km_cumules_debut": 600_000,
    }
    r = client.post("/api/v1/prix", json=config)
    assert r.status_code == 200, r.text
    offre = r.json()
    assert offre["niveau_validation"] == 0
    assert offre["par_brique"]["DL"]["prix_retenu"] == pytest.approx(20_000.0)

    r = client.get("/api/v1/referentiel/journal")
    assert r.status_code == 200
    assert len(r.json()) >= 6  # une entrée par table modifiée + publication


def test_chiffrage_refuse_sans_version_publiee(client: TestClient):
    config = {
        "client_code": "CLIENTOK",
        "serie_code": "VECTRON",
        "km_annuel": 120_000,
        "duree_mois": 24,
        "date_debut": "2026-01-01",
        "age_debut_ans": 5,
        "km_cumules_debut": 600_000,
    }
    r = client.post("/api/v1/prix", json=config)
    assert r.status_code == 409


def test_publication_bloquee_si_locomotive_de_serie_inconnue(client: TestClient):
    numero = client.post("/api/v1/referentiel/brouillons").json()["numero"]
    loco = {
        "numero": "L1",
        "serie_code": "INCONNUE",
        "mise_en_service": "2020-01-01",
        "km_cumules": 0,
        "hm_8_realisee": False,
        "hm_16_realisee": False,
        "statut": "disponible",
        "client_code": None,
    }
    r = client.put(f"/api/v1/referentiel/brouillons/{numero}/flotte/L1", json=loco, headers=HEADERS)
    assert r.status_code == 200, r.text

    r = client.post(f"/api/v1/referentiel/brouillons/{numero}/publier", headers=HEADERS)
    assert r.status_code == 422
    assert r.json()["detail"]["anomalies"]


def _publier(client: TestClient) -> int:
    """`_publier_referentiel_complet` construit un brouillon complet mais ne
    le publie pas (voir le test de cycle de vie, qui vérifie les contrôles
    qualité entre les deux) ; ce raccourci publie directement, pour les
    tests qui ont juste besoin d'un référentiel publié."""

    numero = _publier_referentiel_complet(client)
    r = client.post(f"/api/v1/referentiel/brouillons/{numero}/publier", headers=HEADERS)
    assert r.status_code == 200, r.text
    return numero


def _config_hors_regles() -> dict:
    return {
        "client_code": "CLIENTOK",
        "serie_code": "VECTRON",
        "km_annuel": 120_000,
        "duree_mois": 24,
        "quantite": 1,
        "date_debut": "2026-01-01",
        "age_debut_ans": 5,
        "km_cumules_debut": 600_000,
        "prix_negocies": {"OM": 1_200.0},
    }


def test_demande_de_derogation_calcule_le_niveau_et_le_validateur(client: TestClient, monkeypatch):
    monkeypatch.delenv("POWER_AUTOMATE_WEBHOOK_URL", raising=False)
    _publier(client)

    r = client.post(
        "/api/v1/derogations",
        json={"configuration": _config_hors_regles(), "justification": "remise fidélité"},
        headers=HEADERS,
    )

    assert r.status_code == 200, r.text
    derogation = r.json()
    assert derogation["statut"] == "en_attente"
    assert derogation["niveau"] == 2
    assert derogation["validateur_email"] == "head@akiem.com"
    assert derogation["demandeur"] == "pricing@akiem.com"
    assert derogation["date_decision"] is None


def test_demande_de_derogation_notifie_power_automate(client: TestClient, monkeypatch):
    appels = []

    def faux_post(url, json, timeout):
        appels.append((url, json))

        class FauxReponse:
            status_code = 200

        return FauxReponse()

    monkeypatch.setenv("POWER_AUTOMATE_WEBHOOK_URL", "https://exemple.invalid/webhook")
    monkeypatch.setattr("pricing_engine.derogation.httpx.post", faux_post)
    _publier(client)

    r = client.post(
        "/api/v1/derogations",
        json={"configuration": _config_hors_regles(), "justification": "remise fidélité"},
        headers=HEADERS,
    )

    assert r.status_code == 200, r.text
    assert len(appels) == 1
    url, payload = appels[0]
    assert url == "https://exemple.invalid/webhook"
    assert payload["validateur_email"] == "head@akiem.com"
    assert payload["derogation_id"] == r.json()["id"]


def test_demande_de_derogation_refusee_si_offre_dans_les_regles(client: TestClient):
    _publier(client)
    config = _config_hors_regles()
    config["prix_negocies"] = {}

    r = client.post(
        "/api/v1/derogations",
        json={"configuration": config, "justification": "rien à négocier"},
        headers=HEADERS,
    )

    assert r.status_code == 400


def test_registre_liste_les_demandes(client: TestClient, monkeypatch):
    monkeypatch.delenv("POWER_AUTOMATE_WEBHOOK_URL", raising=False)
    _publier(client)
    client.post(
        "/api/v1/derogations",
        json={"configuration": _config_hors_regles(), "justification": "a"},
        headers=HEADERS,
    )

    r = client.get("/api/v1/derogations")

    assert r.status_code == 200
    assert len(r.json()) == 1


def test_decision_refusee_sans_secret_configure(client: TestClient, monkeypatch):
    monkeypatch.delenv("POWER_AUTOMATE_CALLBACK_SECRET", raising=False)

    r = client.post(
        "/api/v1/derogations/1/decision",
        json={"decision": "approuvee", "decideur": "manager@akiem.com"},
    )

    assert r.status_code == 501


def test_decision_refusee_avec_un_mauvais_secret(client: TestClient, monkeypatch):
    monkeypatch.setenv("POWER_AUTOMATE_CALLBACK_SECRET", "le-bon-secret")

    r = client.post(
        "/api/v1/derogations/1/decision",
        json={"decision": "approuvee", "decideur": "manager@akiem.com"},
        headers={"X-Webhook-Secret": "mauvais-secret"},
    )

    assert r.status_code == 403


def test_decision_approuvee_via_le_webhook_entrant(client: TestClient, monkeypatch):
    monkeypatch.delenv("POWER_AUTOMATE_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("POWER_AUTOMATE_CALLBACK_SECRET", "le-bon-secret")
    _publier(client)
    id_derogation = client.post(
        "/api/v1/derogations",
        json={"configuration": _config_hors_regles(), "justification": "remise fidélité"},
        headers=HEADERS,
    ).json()["id"]

    r = client.post(
        f"/api/v1/derogations/{id_derogation}/decision",
        json={"decision": "approuvee", "decideur": "manager@akiem.com", "commentaire": "ok"},
        headers={"X-Webhook-Secret": "le-bon-secret"},
    )

    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "approuvee"
    assert r.json()["decideur"] == "manager@akiem.com"

    # Et c'est bien persisté dans le registre.
    assert client.get(f"/api/v1/derogations/{id_derogation}").json()["statut"] == "approuvee"


def test_decision_sur_une_derogation_deja_decidee_est_refusee(client: TestClient, monkeypatch):
    monkeypatch.delenv("POWER_AUTOMATE_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("POWER_AUTOMATE_CALLBACK_SECRET", "le-bon-secret")
    _publier(client)
    id_derogation = client.post(
        "/api/v1/derogations",
        json={"configuration": _config_hors_regles(), "justification": "remise fidélité"},
        headers=HEADERS,
    ).json()["id"]
    headers_secret = {"X-Webhook-Secret": "le-bon-secret"}
    client.post(
        f"/api/v1/derogations/{id_derogation}/decision",
        json={"decision": "approuvee", "decideur": "manager@akiem.com"},
        headers=headers_secret,
    )

    r = client.post(
        f"/api/v1/derogations/{id_derogation}/decision",
        json={"decision": "rejetee", "decideur": "manager@akiem.com"},
        headers=headers_secret,
    )

    assert r.status_code == 409
