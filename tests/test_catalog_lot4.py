"""Tests Lot 4 : Quote refondu + QuoteService + chiffrage intégré."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from pricing_engine.catalog.quote import QuoteStatus
from pricing_engine.catalog.quote_store import InMemoryQuoteStore, QuoteService
from pricing_engine.catalog.seed import seed_catalog_akiem
from pricing_engine.catalog.seed_lot2 import seed_lot2
from pricing_engine.catalog.seed_lot3 import seed_lot3
from pricing_engine.catalog.store import InMemoryCatalogStore


@pytest.fixture
def service():
    catalog = InMemoryCatalogStore()
    seed_catalog_akiem(catalog)
    seed_lot2(catalog)
    seed_lot3(catalog)
    quotes = InMemoryQuoteStore()
    return QuoteService(catalog, quotes), quotes


def test_creer_quote_genere_un_numero_sequentiel(service):
    svc, qs = service
    q1 = svc.creer_quote("ACME", "ACME Corp", "kam1@akiem.com")
    q2 = svc.creer_quote("BETA", "Beta SA", "kam1@akiem.com")
    assert q1.quote_number.startswith("Q-")
    assert q2.quote_number.startswith("Q-")
    assert q1.quote_number != q2.quote_number
    assert q1.status == QuoteStatus.DRAFT


def test_ajouter_ligne_execute_le_moteur_v2_et_persiste_le_calcul(service):
    svc, qs = service
    q = svc.creer_quote("ACME", "ACME Corp", "kam1@akiem.com")
    line, calc = svc.ajouter_ligne_et_chiffrer(
        quote_id=q.quote_id,
        technical_variant_code="E186-DABNL",
        country_iso="DE",
        duration_months=24,
        age_years=5,
        annual_mileage_km=150_000,
    )
    assert line.line_number == 1
    assert line.technical_variant_code == "E186-DABNL"
    assert calc.total_monthly > 0
    assert calc.dl_version_label == "2026-v1"
    assert calc.om_version_label == "2026-v1"
    # Le calcul est retrouvable
    calc_from_store = qs.get_pricing_calculation_for_line(line.quote_line_id)
    assert calc_from_store is not None
    assert calc_from_store.pricing_calculation_id == calc.pricing_calculation_id


def test_composants_sont_persistes_pour_explicabilite(service):
    svc, qs = service
    q = svc.creer_quote("ACME", "ACME Corp", "kam1@akiem.com")
    line, calc = svc.ajouter_ligne_et_chiffrer(
        quote_id=q.quote_id,
        technical_variant_code="E186-DABNL",
        country_iso="DE",
        duration_months=24,
        age_years=5,
        annual_mileage_km=150_000,
    )
    composants = qs.list_components(calc.pricing_calculation_id)
    types = {c.component_type for c in composants}
    # Au moins les composants DL et OM principaux
    assert any(t.startswith("dl_") for t in types)
    assert any(t.startswith("om_") for t in types)
    assert any(t == "hm_provision" for t in types)
    # Les composantes HM sont marquées comme non visibles au client
    hm = [c for c in composants if c.component_type == "hm_provision"]
    assert all(not c.is_visible_to_client for c in hm)


def test_totaux_quote_sont_recalcules_a_chaque_ajout(service):
    svc, qs = service
    q = svc.creer_quote("ACME", "ACME Corp", "kam1@akiem.com")
    _, calc1 = svc.ajouter_ligne_et_chiffrer(
        quote_id=q.quote_id, technical_variant_code="E186-DABNL",
        country_iso="DE", duration_months=24, age_years=5, annual_mileage_km=150_000,
        quantity=1,
    )
    q1 = qs.get_quote(q.quote_id)
    assert q1.total_mensuel == pytest.approx(calc1.total_monthly)
    _, calc2 = svc.ajouter_ligne_et_chiffrer(
        quote_id=q.quote_id, technical_variant_code="193-DACHI",
        country_iso="DE", duration_months=24, age_years=3, annual_mileage_km=200_000,
        quantity=2,
    )
    q2 = qs.get_quote(q.quote_id)
    # Total = ligne1 + ligne2 × 2 (quantity)
    assert q2.total_mensuel == pytest.approx(calc1.total_monthly + calc2.total_monthly * 2)


def test_very_high_mileage_fait_monter_le_niveau_de_validation(service):
    svc, qs = service
    q = svc.creer_quote("ACME", "ACME Corp", "kam1@akiem.com")
    _, calc = svc.ajouter_ligne_et_chiffrer(
        quote_id=q.quote_id, technical_variant_code="E186-DABNL",
        country_iso="DE", duration_months=24, age_years=5, annual_mileage_km=250_000,
    )
    # >220k km → warning dérogation → niveau N2 (Head of Pricing)
    assert calc.niveau_validation >= 2


def test_cycle_de_vie_quote_draft_submit_approve(service):
    svc, qs = service
    q = svc.creer_quote("ACME", "ACME Corp", "kam1@akiem.com")
    svc.ajouter_ligne_et_chiffrer(
        quote_id=q.quote_id, technical_variant_code="E186-DABNL",
        country_iso="DE", duration_months=24, age_years=5, annual_mileage_km=150_000,
    )
    assert qs.get_quote(q.quote_id).status == QuoteStatus.DRAFT
    svc.soumettre(q.quote_id, "kam1@akiem.com")
    assert qs.get_quote(q.quote_id).status == QuoteStatus.SUBMITTED
    svc.decider(q.quote_id, "head@akiem.com", approved=True, comment="OK volume")
    assert qs.get_quote(q.quote_id).status == QuoteStatus.APPROVED
    svc.marquer_gagne_ou_perdu(q.quote_id, gagne=True, by="kam1@akiem.com")
    assert qs.get_quote(q.quote_id).status == QuoteStatus.WON


def test_ne_peut_pas_soumettre_une_quote_deja_soumise(service):
    svc, qs = service
    q = svc.creer_quote("ACME", "ACME Corp", "kam1@akiem.com")
    svc.ajouter_ligne_et_chiffrer(
        quote_id=q.quote_id, technical_variant_code="E186-DABNL",
        country_iso="DE", duration_months=24, age_years=5, annual_mileage_km=150_000,
    )
    svc.soumettre(q.quote_id, "kam1@akiem.com")
    with pytest.raises(ValueError, match="statut"):
        svc.soumettre(q.quote_id, "kam1@akiem.com")


def test_le_calcul_reste_fige_meme_si_nouvelle_version_pricebook_publiee(service):
    """Garantie fondamentale (section 8) : la quote fige le prix à son
    émission. Même si on publie DL 2026-v2 après, le calcul reste intact."""
    from pricing_engine.catalog.pricing import PriceBookVersion, PriceBookStatus
    svc, qs = service
    q = svc.creer_quote("ACME", "ACME Corp", "kam1@akiem.com")
    _, calc_avant = svc.ajouter_ligne_et_chiffrer(
        quote_id=q.quote_id, technical_variant_code="E186-DABNL",
        country_iso="DE", duration_months=24, age_years=5, annual_mileage_km=150_000,
    )
    version_gelee = calc_avant.dl_version_label
    total_avant = calc_avant.total_monthly

    # Publie une "nouvelle" version 2026-v2 vide (mais publiée) : les
    # rates n'y existent pas, mais le calcul initial garde sa version
    catalog = svc._catalog
    from datetime import date as _d, datetime as _dt, timezone as _tz
    dl_pb = catalog.get_price_book_by_code("DL_STANDARD")
    catalog.upsert_price_book_version(PriceBookVersion(
        price_book_id=dl_pb.price_book_id, year=2026, version_number=2,
        status=PriceBookStatus.PUBLISHED, valid_from=_d(2026, 7, 1),
        approved_by="head@akiem.com", approved_at=_dt.now(_tz.utc),
        published_at=_dt.now(_tz.utc),
    ))

    # Récupère le calcul persisté : il n'a PAS changé
    calc_apres = qs.get_pricing_calculation_for_line(
        qs.list_quote_lines(q.quote_id)[0].quote_line_id
    )
    assert calc_apres.dl_version_label == version_gelee
    assert calc_apres.total_monthly == total_avant


# =========================================================================
# API endpoints
# =========================================================================


@pytest.fixture
def client():
    from pricing_engine.api import app
    return TestClient(app)


def _login_bearer(client, email, mdp):
    r = client.post("/api/v1/auth/login", json={"email": email, "mot_de_passe": mdp})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_api_create_quote_and_add_line(client):
    auth = _login_bearer(client, "kam1@akiem.com", "kam")

    # Créer la quote
    r = client.post("/api/v1/catalog/quotes",
        json={"client_code": "ACME", "client_name": "ACME Corp"},
        headers=auth)
    assert r.status_code == 200, r.text
    quote = r.json()
    assert quote["client_code"] == "ACME"
    assert quote["status"] == "draft"
    assert quote["created_by"].lower() == "kam1@akiem.com"
    quote_id = quote["quote_id"]

    # Ajouter une ligne → chiffrage automatique
    r = client.post(f"/api/v1/catalog/quotes/{quote_id}/lines",
        json={
            "technical_variant_code": "E186-DABNL",
            "country_iso": "DE",
            "duration_months": 24,
            "age_years": 5,
            "annual_mileage_km": 150_000,
        },
        headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["line"]["technical_variant_code"] == "E186-DABNL"
    assert data["calculation"]["total_monthly"] > 0
    assert data["calculation"]["dl_version_label"] == "2026-v1"


def test_api_kam_voit_uniquement_ses_propres_quotes(client):
    auth_k1 = _login_bearer(client, "kam1@akiem.com", "kam")
    auth_k2 = _login_bearer(client, "kam2@akiem.com", "kam")
    auth_admin = _login_bearer(client, "admin@akiem.com", "admin")

    # KAM1 crée 2 quotes
    for _ in range(2):
        client.post("/api/v1/catalog/quotes",
            json={"client_code": "ACME", "client_name": "ACME"}, headers=auth_k1)
    # KAM2 crée 1 quote
    client.post("/api/v1/catalog/quotes",
        json={"client_code": "BETA", "client_name": "BETA"}, headers=auth_k2)

    # KAM1 voit uniquement les siennes
    r = client.get("/api/v1/catalog/quotes", headers=auth_k1)
    kam1_quotes = r.json()
    assert all(q["created_by"].lower() == "kam1@akiem.com" for q in kam1_quotes)

    # KAM2 pareil
    r = client.get("/api/v1/catalog/quotes", headers=auth_k2)
    assert all(q["created_by"].lower() == "kam2@akiem.com" for q in r.json())

    # ADMIN voit TOUT
    r = client.get("/api/v1/catalog/quotes", headers=auth_admin)
    assert len(r.json()) >= 3


def test_api_submit_et_decision(client):
    auth_kam = _login_bearer(client, "kam1@akiem.com", "kam")
    auth_direction = _login_bearer(client, "direction@akiem.com", "direction")

    r = client.post("/api/v1/catalog/quotes",
        json={"client_code": "ACME", "client_name": "ACME"}, headers=auth_kam)
    quote_id = r.json()["quote_id"]
    client.post(f"/api/v1/catalog/quotes/{quote_id}/lines",
        json={"technical_variant_code": "E186-DABNL", "country_iso": "DE",
              "duration_months": 24, "age_years": 5, "annual_mileage_km": 150_000},
        headers=auth_kam)
    # Submit
    r = client.post(f"/api/v1/catalog/quotes/{quote_id}/submit", headers=auth_kam)
    assert r.status_code == 200
    assert r.json()["status"] == "submitted"
    # KAM n'a pas la permission decider_derogation
    r = client.post(f"/api/v1/catalog/quotes/{quote_id}/decision",
        json={"approved": True}, headers=auth_kam)
    assert r.status_code == 403
    # Direction oui
    r = client.post(f"/api/v1/catalog/quotes/{quote_id}/decision",
        json={"approved": True, "comment": "OK pour cette fois"}, headers=auth_direction)
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert r.json()["decided_by"].lower() == "direction@akiem.com"


def test_api_get_quote_renvoie_lignes_et_calculs_et_composants(client):
    auth = _login_bearer(client, "kam1@akiem.com", "kam")
    r = client.post("/api/v1/catalog/quotes",
        json={"client_code": "ACME", "client_name": "ACME"}, headers=auth)
    qid = r.json()["quote_id"]
    client.post(f"/api/v1/catalog/quotes/{qid}/lines",
        json={"technical_variant_code": "E186-DABNL", "country_iso": "DE",
              "duration_months": 24, "age_years": 5, "annual_mileage_km": 150_000},
        headers=auth)
    r = client.get(f"/api/v1/catalog/quotes/{qid}", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert len(data["lines"]) == 1
    assert data["lines"][0]["calculation"] is not None
    assert len(data["lines"][0]["components"]) > 0
