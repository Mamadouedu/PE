"""Tests Lot 2 : UsageProfiles, MileageBands, Maintenance, ECM, ServiceLevels."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pricing_engine.catalog.maintenance import (
    MaintenanceOperation,
    OperationType,
    TriggerType,
)
from pricing_engine.catalog.seed import seed_catalog_akiem
from pricing_engine.catalog.seed_lot2 import seed_lot2
from pricing_engine.catalog.store import InMemoryCatalogStore
from pricing_engine.catalog.usage import (
    CalculationMethod,
    MileageBand,
    UsageProfile,
    UtilisationType,
)


# =========================================================================
# Unit tests : MileageBand.contient()
# =========================================================================


def test_mileage_band_contient_dans_lintervalle():
    band = MileageBand(
        band_code="OM_080_120", band_name="80-120",
        min_annual_mileage_km=80_000, max_annual_mileage_km=120_000,
    )
    assert not band.contient(79_999)
    assert band.contient(80_000)
    assert band.contient(119_999)
    assert not band.contient(120_000)


def test_mileage_band_sans_borne_haute_couvre_tout_au_dessus():
    band = MileageBand(
        band_code="OM_240_PLUS", band_name="240+",
        min_annual_mileage_km=240_000, max_annual_mileage_km=None,
    )
    assert band.contient(240_000)
    assert band.contient(500_000)
    assert not band.contient(239_999)


# =========================================================================
# Seed Lot 2
# =========================================================================


def test_seed_lot2_cree_les_entites():
    store = InMemoryCatalogStore()
    seed_catalog_akiem(store)
    seed_lot2(store)

    assert len(store.list_usage_profiles()) == 6
    assert len(store.list_mileage_bands()) == 6
    assert len(store.list_engine_hours_bands()) == 5
    assert len(store.list_maintenance_operations()) == 7
    assert len(store.list_maintenance_plans()) == 4
    assert len(store.list_ecm_providers()) == 5
    assert len(store.list_service_levels()) == 4


def test_seed_lot2_profils_ont_les_bons_seuils_mileage():
    store = InMemoryCatalogStore()
    seed_catalog_akiem(store)
    seed_lot2(store)
    standard = store.get_usage_profile_by_code("STANDARD_MILEAGE")
    assert standard is not None
    assert standard.annual_mileage_min_km == 80_000
    assert standard.annual_mileage_max_km == 160_000
    assert standard.utilisation_type == UtilisationType.FREIGHT


def test_resolution_palier_mileage_pour_offre():
    """Dans une offre à 150 000 km/an, on doit tomber dans OM_120_160."""
    store = InMemoryCatalogStore()
    seed_catalog_akiem(store)
    seed_lot2(store)
    band = store.get_mileage_band_for_annual_km(150_000)
    assert band is not None
    assert band.band_code == "OM_120_160"


def test_plan_standard_traxx_contient_hm1_hm2_hm3():
    store = InMemoryCatalogStore()
    seed_catalog_akiem(store)
    seed_lot2(store)
    plans = {p.plan_code: p for p in store.list_maintenance_plans()}
    traxx = plans["TRAXX_MS_STANDARD"]
    ops = store.list_operations_for_plan(traxx.maintenance_plan_id)
    codes = {o.operation_code for o in ops}
    assert {"HM1", "HM2", "HM3", "VGI", "WHEEL_REPROFILING"} == codes


def test_eurodual_plan_contient_diesel_overhaul():
    """Le plan Eurodual (dual-mode) doit inclure la révision moteur
    thermique — pas les plans pur électrique."""
    store = InMemoryCatalogStore()
    seed_catalog_akiem(store)
    seed_lot2(store)
    plans = {p.plan_code: p for p in store.list_maintenance_plans()}
    eurodual_ops = store.list_operations_for_plan(plans["EURODUAL_STANDARD"].maintenance_plan_id)
    assert any(o.operation_code == "DIESEL_OVERHAUL" for o in eurodual_ops)
    traxx_ops = store.list_operations_for_plan(plans["TRAXX_MS_STANDARD"].maintenance_plan_id)
    assert not any(o.operation_code == "DIESEL_OVERHAUL" for o in traxx_ops)


def test_variante_e186_dabnl_supporte_tous_les_profils_dusage():
    store = InMemoryCatalogStore()
    seed_catalog_akiem(store)
    seed_lot2(store)
    variant = store.get_variant_by_code("E186-DABNL")
    rows = store.list_usage_profiles_for_variant(variant.technical_variant_id)
    codes = {profile.usage_profile_code for profile, _link in rows}
    # Au moins les 4 profils fret standards
    assert {"LOW_MILEAGE", "STANDARD_MILEAGE", "HIGH_MILEAGE", "VERY_HIGH_MILEAGE"}.issubset(codes)


def test_very_high_mileage_exige_approbation_specifique():
    """La règle métier : au-delà de 220k km/an, dérogation obligatoire."""
    store = InMemoryCatalogStore()
    seed_catalog_akiem(store)
    seed_lot2(store)
    variant = store.get_variant_by_code("E186-DABNL")
    rows = store.list_usage_profiles_for_variant(variant.technical_variant_id)
    vhm_link = next(link for profile, link in rows if profile.usage_profile_code == "VERY_HIGH_MILEAGE")
    assert vhm_link.requires_specific_approval is True


# =========================================================================
# Tests des endpoints REST Lot 2
# =========================================================================


@pytest.fixture
def client():
    from pricing_engine.api import app
    return TestClient(app)


def test_api_list_usage_profiles(client):
    r = client.get("/api/v1/catalog/usage-profiles")
    assert r.status_code == 200
    codes = {p["usage_profile_code"] for p in r.json()}
    assert "STANDARD_MILEAGE" in codes
    assert "VERY_HIGH_MILEAGE" in codes


def test_api_get_band_for_annual_km(client):
    r = client.get("/api/v1/catalog/mileage-bands/for-annual-km/150000")
    assert r.status_code == 200
    assert r.json()["band_code"] == "OM_120_160"


def test_api_get_band_hors_bornes_retourne_404(client):
    # Le seed commence à 0, donc -1 ne doit pas tomber dans un palier
    r = client.get("/api/v1/catalog/mileage-bands/for-annual-km/-1")
    assert r.status_code == 404


def test_api_list_maintenance_operations(client):
    r = client.get("/api/v1/catalog/maintenance-operations")
    assert r.status_code == 200
    codes = {o["operation_code"] for o in r.json()}
    assert {"HM1", "HM2", "HM3", "VGI", "WHEEL_REPROFILING"}.issubset(codes)


def test_api_variant_usage_profiles(client):
    # Récupère E186-DABNL
    r = client.get("/api/v1/catalog/technical-variants")
    variant = next(v for v in r.json() if v["variant_code"] == "E186-DABNL")
    r = client.get(f"/api/v1/catalog/technical-variants/{variant['technical_variant_id']}/usage-profiles")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 4  # au moins 4 profils fret


def test_api_list_ecm_providers_contient_akiem(client):
    r = client.get("/api/v1/catalog/ecm-providers")
    assert r.status_code == 200
    codes = {p["provider_code"] for p in r.json()}
    assert "AMS" in codes


def test_api_list_service_levels(client):
    r = client.get("/api/v1/catalog/service-levels")
    assert r.status_code == 200
    codes = {s["service_level_code"] for s in r.json()}
    assert "BASIC" in codes and "PREMIUM" in codes


def test_api_variant_maintenance_plans(client):
    r = client.get("/api/v1/catalog/technical-variants")
    traxx_var = next(v for v in r.json() if v["variant_code"].startswith("E186"))
    r = client.get(f"/api/v1/catalog/technical-variants/{traxx_var['technical_variant_id']}/maintenance-plans")
    assert r.status_code == 200
    plans = r.json()
    assert any(p["plan_code"] == "TRAXX_MS_STANDARD" for p in plans)
