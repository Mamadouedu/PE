"""Tests Lot 5 : FleetAssets + relevés compteurs + historique maintenance."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from pricing_engine.catalog.fleet import (
    AssetMaintenanceHistoryEntry,
    AssetMeterReading,
    FleetAsset,
    MaintenanceEventStatus,
    OperationalStatus,
    OwnershipStatus,
)
from pricing_engine.catalog.seed import seed_catalog_akiem
from pricing_engine.catalog.seed_lot2 import seed_lot2
from pricing_engine.catalog.seed_lot5 import seed_lot5
from pricing_engine.catalog.store import InMemoryCatalogStore


@pytest.fixture
def store_lot5():
    """Store avec Lot 1 + Lot 2 (pour les ops de maintenance) + Lot 5."""
    s = InMemoryCatalogStore()
    seed_catalog_akiem(s)
    seed_lot2(s)
    seed_lot5(s)
    return s


# =========================================================================
# Modèle FleetAsset
# =========================================================================


def test_fleet_asset_age_years_se_calcule_depuis_commissioning_date():
    a = FleetAsset(
        asset_number="AK-TEST",
        vehicle_registration_number="91 80 6186 999-0 D-AKIEM",
        technical_variant_id=__import__("uuid").uuid4(),
        manufacturing_year=2020,
        commissioning_date=date(2020, 1, 1),
    )
    assert abs(a.age_years(at_date=date(2026, 1, 1)) - 6.0) < 0.01


# =========================================================================
# Store
# =========================================================================


def test_upsert_fleet_asset_refuse_variante_inconnue():
    from uuid import uuid4
    s = InMemoryCatalogStore()
    seed_catalog_akiem(s)
    with pytest.raises(ValueError, match="TechnicalVariant"):
        s.upsert_fleet_asset(FleetAsset(
            asset_number="AK-GHOST", vehicle_registration_number="91 80 9999 999-9 D-AKIEM",
            technical_variant_id=uuid4(), manufacturing_year=2020,
            commissioning_date=date(2020, 1, 1),
        ))


def test_meter_reading_met_a_jour_compteur_courant(store_lot5):
    asset = store_lot5.get_fleet_asset_by_asset_number("AK-00201")
    assert asset is not None
    km_initial = asset.current_mileage_km
    # Nouveau relevé 50k km au-dessus
    nouveau_km = km_initial + 50_000
    store_lot5.add_meter_reading(AssetMeterReading(
        fleet_asset_id=asset.fleet_asset_id,
        reading_date=date.today(),
        mileage_km=nouveau_km,
    ))
    asset_after = store_lot5.get_fleet_asset(asset.fleet_asset_id)
    assert asset_after.current_mileage_km == nouveau_km


def test_meter_reading_ne_met_pas_a_jour_si_recul_du_compteur(store_lot5):
    """Le compteur est monotone croissant : un relevé en-dessous ne doit
    pas écraser la valeur actuelle (anti-fraude / anti-erreur)."""
    asset = store_lot5.get_fleet_asset_by_asset_number("AK-00201")
    km_initial = asset.current_mileage_km
    store_lot5.add_meter_reading(AssetMeterReading(
        fleet_asset_id=asset.fleet_asset_id,
        reading_date=date.today(),
        mileage_km=km_initial - 10_000,  # Recul
    ))
    assert store_lot5.get_fleet_asset(asset.fleet_asset_id).current_mileage_km == km_initial


def test_maintenance_history_met_a_jour_last_hm_date(store_lot5):
    asset = store_lot5.get_fleet_asset_by_asset_number("AK-00203")
    ops = {o.operation_code: o for o in store_lot5.list_maintenance_operations()}
    hm2 = ops["HM2"]

    new_date = date.today() - timedelta(days=15)
    store_lot5.add_maintenance_history(AssetMaintenanceHistoryEntry(
        fleet_asset_id=asset.fleet_asset_id,
        operation_id=hm2.operation_id,
        operation_code="HM2",
        status=MaintenanceEventStatus.COMPLETED,
        completed_at=new_date,
        workshop_name="Akiem Oberursel",
        workshop_country_iso="DE",
    ))
    assert store_lot5.get_fleet_asset(asset.fleet_asset_id).last_hm2_date == new_date


# =========================================================================
# Seed Lot 5
# =========================================================================


def test_seed_lot5_cree_une_flotte_variee(store_lot5):
    assets = store_lot5.list_fleet_assets()
    assert len(assets) == 17
    # Au moins une loco par grande famille
    variant_codes = {store_lot5.get_technical_variant(a.technical_variant_id).variant_code for a in assets}
    assert "E186-DABNL" in variant_codes
    assert "193-DACHI" in variant_codes
    assert "159-DABF" in variant_codes


def test_seed_lot5_cree_des_statuts_operationnels_varies(store_lot5):
    assets = store_lot5.list_fleet_assets()
    statuses = {a.operational_status for a in assets}
    # Doit contenir plusieurs statuts
    assert len(statuses) >= 3


def test_seed_lot5_filtre_par_variante(store_lot5):
    variant = store_lot5.get_variant_by_code("E186-DABNL")
    assets = store_lot5.list_fleet_assets(variant_id=variant.technical_variant_id)
    # Au moins 2 locos E186-DABNL seedées (AK-00201, AK-00202, AK-00203)
    assert len(assets) >= 2


def test_seed_lot5_cree_relevés_et_historique(store_lot5):
    asset = store_lot5.get_fleet_asset_by_asset_number("AK-00201")
    readings = store_lot5.list_meter_readings(asset.fleet_asset_id)
    assert len(readings) >= 2
    history = store_lot5.list_maintenance_history(asset.fleet_asset_id)
    assert len(history) >= 1


# =========================================================================
# Summary (vue agrégée pour UI)
# =========================================================================


def test_summary_calcule_les_prochaines_hm(store_lot5):
    asset = store_lot5.get_fleet_asset_by_asset_number("AK-00201")
    summary = store_lot5.compute_fleet_asset_summary(asset.fleet_asset_id)
    assert summary is not None
    assert summary.asset_number == "AK-00201"
    # Prochaine HM doit être postérieure au km courant
    assert summary.next_hm2_due_km >= asset.current_mileage_km
    # Km restant avant prochaine HM doit être positif
    assert summary.km_until_next_hm is not None
    assert summary.km_until_next_hm >= 0


def test_summary_inclut_age_et_pays_courant(store_lot5):
    asset = store_lot5.get_fleet_asset_by_asset_number("AK-00401")
    summary = store_lot5.compute_fleet_asset_summary(asset.fleet_asset_id)
    assert summary.age_years > 0
    assert summary.manufacturing_year == 2021
    # Les E188-DACHI sont homologuées DE+AT+CH+IT, le pays courant est l'un de ceux-là
    assert summary.current_country_iso in {"DE", "AT", "CH", "IT"}


# =========================================================================
# API endpoints
# =========================================================================


@pytest.fixture
def client():
    from pricing_engine.api import app
    return TestClient(app)


def test_api_list_fleet_assets(client):
    r = client.get("/api/v1/catalog/fleet-assets")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 10
    asset_numbers = {a["asset_number"] for a in data}
    assert "AK-00201" in asset_numbers


def test_api_fleet_asset_summary(client):
    # D'abord récupérer un id
    r = client.get("/api/v1/catalog/fleet-assets")
    first = next(a for a in r.json() if a["asset_number"] == "AK-00201")
    r = client.get(f"/api/v1/catalog/fleet-assets/{first['fleet_asset_id']}/summary")
    assert r.status_code == 200
    s = r.json()
    assert s["asset_number"] == "AK-00201"
    assert s["technical_variant_code"] == "E186-DABNL"
    assert s["age_years"] > 0


def test_api_meter_readings_listing(client):
    r = client.get("/api/v1/catalog/fleet-assets")
    first = next(a for a in r.json() if a["asset_number"] == "AK-00201")
    r = client.get(f"/api/v1/catalog/fleet-assets/{first['fleet_asset_id']}/meter-readings")
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_api_maintenance_history_listing(client):
    r = client.get("/api/v1/catalog/fleet-assets")
    first = next(a for a in r.json() if a["asset_number"] == "AK-00201")
    r = client.get(f"/api/v1/catalog/fleet-assets/{first['fleet_asset_id']}/maintenance-history")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_api_filtre_par_statut_operationnel(client):
    r = client.get("/api/v1/catalog/fleet-assets?operational_status=in_maintenance")
    assert r.status_code == 200
    data = r.json()
    assert all(a["operational_status"] == "in_maintenance" for a in data)
    # Au moins une loco en maintenance dans le seed (AK-00203)
    assert any(a["asset_number"] == "AK-00203" for a in data)
