"""Tests Lot 3 : PriceBooks, tarifs versionnés et moteur de prix v2."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pricing_engine.catalog.pricing import (
    AssetAgeBand,
    LeaseBand,
    OperatingMaintenanceRate,
    PriceBookStatus,
    calculer_om_mensuel,
)
from pricing_engine.catalog.pricing_engine_v2 import DemandeChiffrage, MoteurPrixV2
from pricing_engine.catalog.seed import seed_catalog_akiem
from pricing_engine.catalog.seed_lot2 import seed_lot2
from pricing_engine.catalog.seed_lot3 import seed_lot3
from pricing_engine.catalog.store import InMemoryCatalogStore


@pytest.fixture
def store_complet():
    """Store avec Lot 1 + Lot 2 + Lot 3 appliqués."""
    s = InMemoryCatalogStore()
    seed_catalog_akiem(s)
    seed_lot2(s)
    seed_lot3(s)
    return s


# =========================================================================
# Unit tests sur les paliers
# =========================================================================


def test_lease_band_contient():
    lb = LeaseBand(band_code="MEDIUM", band_name="Medium",
                   min_duration_months=12, max_duration_months=36)
    assert not lb.contient(11)
    assert lb.contient(12)
    assert lb.contient(36)
    assert not lb.contient(37)


def test_asset_age_band_contient():
    ab = AssetAgeBand(band_code="YOUNG", band_name="Young",
                      min_age_years=5, max_age_years=10)
    assert not ab.contient(4.9)
    assert ab.contient(5.0)
    assert ab.contient(9.99)
    assert not ab.contient(10.0)


def test_asset_age_band_sans_borne_haute():
    old = AssetAgeBand(band_code="OLD", band_name="Old",
                       min_age_years=15, max_age_years=None)
    assert old.contient(15)
    assert old.contient(99)


# =========================================================================
# Formule OM (section 11)
# =========================================================================


def test_formule_om_canonique():
    """OM = monthly_fixed + (km × per_km / 12) + (h × per_h / 12) + ecm + lastmile."""
    from uuid import uuid4
    rate = OperatingMaintenanceRate(
        price_book_version_id=uuid4(),
        technical_variant_id=uuid4(),
        mileage_band_id=uuid4(),
        monthly_fixed_amount=2000,
        price_per_kilometer=0.08,
        price_per_engine_hour=0,
        ecm_monthly_amount=250,
        last_mile_monthly_amount=0,
    )
    detail = calculer_om_mensuel(rate, annual_mileage_km=120_000, annual_engine_hours=0)
    # 2000 + (120000 × 0.08 / 12) + 0 + 250 + 0 = 2000 + 800 + 250 = 3050
    assert detail["total_monthly"] == 3050
    assert detail["monthly_fixed"] == 2000
    assert detail["mileage_component"] == 800
    assert detail["ecm_monthly"] == 250


def test_formule_om_applique_le_plancher():
    """Le minimum_monthly_amount force un plancher."""
    from uuid import uuid4
    rate = OperatingMaintenanceRate(
        price_book_version_id=uuid4(),
        technical_variant_id=uuid4(),
        mileage_band_id=uuid4(),
        monthly_fixed_amount=100,
        price_per_kilometer=0.001,
        minimum_monthly_amount=500,
    )
    detail = calculer_om_mensuel(rate, annual_mileage_km=50_000)
    # 100 + (50000 × 0.001 / 12) = 100 + 4.17 ≈ 104 < plancher 500
    assert detail["total_monthly"] == 500
    assert "floor_applied" in detail


def test_formule_om_applique_le_cap_annuel():
    from uuid import uuid4
    rate = OperatingMaintenanceRate(
        price_book_version_id=uuid4(),
        technical_variant_id=uuid4(),
        mileage_band_id=uuid4(),
        monthly_fixed_amount=0,
        price_per_kilometer=10,
        maximum_annual_amount=600_000,
    )
    detail = calculer_om_mensuel(rate, annual_mileage_km=200_000)
    # 200000 × 10 / 12 = 166 666 par mois = 2M/an > cap 600k → cap appliqué
    # Cap mensuel = 50 000
    assert detail["total_monthly"] == 50_000
    assert "cap_applied" in detail


# =========================================================================
# Seed Lot 3
# =========================================================================


def test_seed_lot3_cree_tarifs_pour_toutes_variantes(store_complet):
    assert len(store_complet.list_lease_bands()) == 4
    assert len(store_complet.list_asset_age_bands()) == 4
    assert len(store_complet.list_country_groups()) == 6
    assert len(store_complet.list_commercial_options()) == 7
    assert len(store_complet.list_price_books()) == 3
    # Au moins 1 version par PriceBook
    for pb in store_complet.list_price_books():
        versions = store_complet.list_price_book_versions(price_book_id=pb.price_book_id)
        assert len(versions) >= 1
        assert any(v.status == PriceBookStatus.PUBLISHED for v in versions)

    # Pour 15 variantes × 6 country_groups × 4 lease × 4 age = 1440 DL rates
    assert len(store_complet.list_dry_lease_rates()) == 1440
    # 15 variantes × 6 opérations communes = 90 + bonus EURODUAL = 92
    assert len(store_complet.list_heavy_maintenance_rates()) >= 90
    # 15 variantes × 6 paliers mileage = 90 OM rates
    assert len(store_complet.list_operating_maintenance_rates()) == 90


def test_resolution_country_group(store_complet):
    cg = store_complet.get_country_group_for_iso("DE")
    assert cg is not None
    assert cg.group_code == "CORE_DACH"
    cg2 = store_complet.get_country_group_for_iso("PL")
    assert cg2.group_code == "FRET_EST"


# =========================================================================
# Moteur de prix v2
# =========================================================================


def test_moteur_v2_chiffre_une_offre_standard(store_complet):
    moteur = MoteurPrixV2(store_complet)
    res = moteur.chiffrer(DemandeChiffrage(
        technical_variant_code="E186-DABNL",
        country_iso="DE",
        duration_months=24,
        age_years=5,
        annual_mileage_km=150_000,
    ))
    assert res.dl_mensuel is not None
    assert res.dl_mensuel > 20_000
    assert res.om_mensuel > 2_000
    assert res.total_mensuel == pytest.approx(res.dl_mensuel + res.hm_mensuel_provisionne + res.om_mensuel)
    assert res.detail_om["mileage_band"] == "OM_120_160"
    assert res.detail_dl["lease_band"] == "MEDIUM"
    assert res.detail_dl["asset_age_band"] == "YOUNG"
    assert res.detail_dl["country_group"] == "CORE_DACH"


def test_moteur_v2_le_mileage_eleve_declenche_warning(store_complet):
    moteur = MoteurPrixV2(store_complet)
    res = moteur.chiffrer(DemandeChiffrage(
        technical_variant_code="E186-DABNL",
        country_iso="DE",
        duration_months=36,
        age_years=5,
        annual_mileage_km=240_000,  # > 220k → warning
    ))
    assert any("dérogation requise" in w for w in res.warnings)


def test_moteur_v2_pays_fret_est_moins_cher_que_dach(store_complet):
    """Les multiplicateurs pays du seed Lot 3 : PL (FRET_EST, 0.92) < DE (CORE_DACH, 1.10)."""
    moteur = MoteurPrixV2(store_complet)
    de = moteur.chiffrer(DemandeChiffrage(
        technical_variant_code="E186-DABNL", country_iso="DE",
        duration_months=24, age_years=5, annual_mileage_km=150_000,
    ))
    pl = moteur.chiffrer(DemandeChiffrage(
        technical_variant_code="193-DABNL", country_iso="PL",
        duration_months=24, age_years=5, annual_mileage_km=150_000,
    ))
    # Le DL doit être plus bas en Pologne
    assert pl.dl_mensuel < de.dl_mensuel


def test_moteur_v2_locomotive_ancienne_moins_chere(store_complet):
    """Multiplicateur âge : OLD (0.78) < NEW (1.10)."""
    moteur = MoteurPrixV2(store_complet)
    neuve = moteur.chiffrer(DemandeChiffrage(
        technical_variant_code="E186-DABNL", country_iso="DE",
        duration_months=24, age_years=2, annual_mileage_km=150_000,
    ))
    ancienne = moteur.chiffrer(DemandeChiffrage(
        technical_variant_code="E186-DABNL", country_iso="DE",
        duration_months=24, age_years=18, annual_mileage_km=150_000,
    ))
    assert ancienne.dl_mensuel < neuve.dl_mensuel


def test_moteur_v2_variante_inconnue_leve_une_erreur(store_complet):
    moteur = MoteurPrixV2(store_complet)
    with pytest.raises(ValueError, match="inconnue"):
        moteur.chiffrer(DemandeChiffrage(
            technical_variant_code="FANTOME-XXX", country_iso="DE",
            duration_months=24, age_years=5, annual_mileage_km=120_000,
        ))


def test_moteur_v2_eurodual_a_un_tarif_diesel_overhaul(store_complet):
    """Section seed Lot 2 : EURODUAL inclut DIESEL_OVERHAUL dans son plan.
    Lot 3 : les HM rates doivent couvrir cette opération pour EURODUAL."""
    moteur = MoteurPrixV2(store_complet)
    res = moteur.chiffrer(DemandeChiffrage(
        technical_variant_code="159-DACH", country_iso="CH",
        duration_months=36, age_years=3, annual_mileage_km=100_000,
    ))
    assert any(d["operation_code"] == "DIESEL_OVERHAUL" for d in res.detail_hm)


# =========================================================================
# API Lot 3
# =========================================================================


@pytest.fixture
def client():
    from pricing_engine.api import app
    return TestClient(app)


def test_api_list_price_books(client):
    r = client.get("/api/v1/catalog/price-books")
    assert r.status_code == 200
    codes = {pb["price_book_code"] for pb in r.json()}
    assert {"DL_STANDARD", "HM_STANDARD", "OM_STANDARD"}.issubset(codes)


def test_api_list_country_groups(client):
    r = client.get("/api/v1/catalog/country-groups")
    assert r.status_code == 200
    codes = {g["group_code"] for g in r.json()}
    assert "CORE_DACH" in codes


def test_api_list_commercial_options(client):
    r = client.get("/api/v1/catalog/commercial-options")
    assert r.status_code == 200
    codes = {o["option_code"] for o in r.json()}
    assert {"ECM_SERVICE", "LAST_MILE", "HOTLINE_24_7"}.issubset(codes)


def test_api_chiffrage_end_to_end(client):
    r = client.post("/api/v1/catalog/chiffrage", json={
        "technical_variant_code": "E186-DABNL",
        "country_iso": "DE",
        "duration_months": 24,
        "age_years": 5,
        "annual_mileage_km": 150_000,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["variant_code"] == "E186-DABNL"
    assert data["total_mensuel"] > 0
    assert data["detail_om"]["mileage_band"] == "OM_120_160"
    assert "2026-v1" in data["versions_utilisees"].values()


def test_api_chiffrage_variante_inconnue_retourne_422(client):
    r = client.post("/api/v1/catalog/chiffrage", json={
        "technical_variant_code": "INEXISTANTE",
        "country_iso": "DE",
        "duration_months": 24,
        "age_years": 5,
        "annual_mileage_km": 150_000,
    })
    assert r.status_code == 422
