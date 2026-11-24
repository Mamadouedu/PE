"""Tests end-to-end API en mode SQL complet (Lots 1→5).

Lance l'API avec `CATALOG_DATABASE_URL=sqlite:///...` et vérifie que :
- le catalog persiste
- les quotes se créent, se chiffrent et se persistent
- le fleet (locomotives, relevés, historique) persiste
- un redémarrage conserve tout
"""

from __future__ import annotations

import importlib
import os
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pricing_engine.catalog.db import create_all_catalog_tables
from pricing_engine.catalog.fleet import FleetAsset, OperationalStatus, OwnershipStatus
from pricing_engine.catalog.seed import seed_catalog_akiem
from pricing_engine.catalog.seed_lot2 import seed_lot2
from pricing_engine.catalog.seed_lot3 import seed_lot3
from pricing_engine.catalog.seed_lot5 import seed_lot5
from pricing_engine.catalog.sql_store import SqlAlchemyCatalogStore


@pytest.fixture
def sql_store_lot5():
    engine = create_engine("sqlite:///:memory:", future=True)
    create_all_catalog_tables(engine)
    sf = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    store = SqlAlchemyCatalogStore(sf)
    seed_catalog_akiem(store)
    seed_lot2(store)
    seed_lot3(store)
    seed_lot5(store)
    return store


# =========================================================================
# SqlAlchemyCatalogStore — Lot 5 Fleet
# =========================================================================


def test_sql_fleet_assets_persistes(sql_store_lot5):
    assets = sql_store_lot5.list_fleet_assets()
    assert len(assets) == 17
    numbers = {a.asset_number for a in assets}
    assert "AK-00201" in numbers


def test_sql_fleet_asset_summary(sql_store_lot5):
    asset = sql_store_lot5.get_fleet_asset_by_asset_number("AK-00201")
    summary = sql_store_lot5.compute_fleet_asset_summary(asset.fleet_asset_id)
    assert summary is not None
    assert summary.technical_variant_code == "E186-DABNL"
    assert summary.age_years > 0
    assert summary.next_hm2_due_km > 0


def test_sql_meter_reading_monotone(sql_store_lot5):
    """Règle anti-fraude : un relevé en-dessous du compteur courant ne
    doit pas l'écraser. Pareil qu'in-memory."""
    from pricing_engine.catalog.fleet import AssetMeterReading
    asset = sql_store_lot5.get_fleet_asset_by_asset_number("AK-00201")
    km_initial = asset.current_mileage_km

    sql_store_lot5.add_meter_reading(AssetMeterReading(
        fleet_asset_id=asset.fleet_asset_id,
        reading_date=date.today(),
        mileage_km=km_initial - 10_000,  # Recul interdit
    ))
    assert sql_store_lot5.get_fleet_asset(asset.fleet_asset_id).current_mileage_km == km_initial

    sql_store_lot5.add_meter_reading(AssetMeterReading(
        fleet_asset_id=asset.fleet_asset_id,
        reading_date=date.today(),
        mileage_km=km_initial + 50_000,  # Croissant OK
    ))
    assert sql_store_lot5.get_fleet_asset(asset.fleet_asset_id).current_mileage_km == km_initial + 50_000


def test_sql_maintenance_history_met_a_jour_last_date(sql_store_lot5):
    from pricing_engine.catalog.fleet import AssetMaintenanceHistoryEntry, MaintenanceEventStatus
    asset = sql_store_lot5.get_fleet_asset_by_asset_number("AK-00203")
    ops = {o.operation_code: o for o in sql_store_lot5.list_maintenance_operations()}
    hm2 = ops["HM2"]
    new_date = date(2026, 10, 15)
    sql_store_lot5.add_maintenance_history(AssetMaintenanceHistoryEntry(
        fleet_asset_id=asset.fleet_asset_id,
        operation_id=hm2.operation_id,
        operation_code="HM2",
        status=MaintenanceEventStatus.COMPLETED,
        completed_at=new_date,
    ))
    assert sql_store_lot5.get_fleet_asset(asset.fleet_asset_id).last_hm2_date == new_date


# =========================================================================
# API en mode SQL : bascule dynamique
# =========================================================================


@pytest.fixture
def sql_api_client(tmp_path):
    """Lance l'API avec CATALOG_DATABASE_URL sur un fichier SQLite isolé."""
    db_file = tmp_path / "e2e.db"
    url = f"sqlite:///{db_file}"
    old = os.environ.get("CATALOG_DATABASE_URL")
    os.environ["CATALOG_DATABASE_URL"] = url
    # Reload le module api pour que le switch dynamique capture la nouvelle URL
    import pricing_engine.api as api_module
    importlib.reload(api_module)
    client = TestClient(api_module.app)
    yield client, api_module, url
    # Cleanup
    if old is None:
        os.environ.pop("CATALOG_DATABASE_URL", None)
    else:
        os.environ["CATALOG_DATABASE_URL"] = old
    importlib.reload(api_module)


def _login(client, email, mdp):
    r = client.post("/api/v1/auth/login", json={"email": email, "mot_de_passe": mdp})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_api_sql_mode_chiffrage(sql_api_client):
    client, _, _ = sql_api_client
    r = client.post("/api/v1/catalog/chiffrage", json={
        "technical_variant_code": "E186-DABNL",
        "country_iso": "DE",
        "duration_months": 24,
        "age_years": 5,
        "annual_mileage_km": 150_000,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["total_mensuel"] > 0
    # Bit-à-bit identique à l'in-memory
    assert data["dl_mensuel"] == pytest.approx(25289.0, rel=0.01)


def test_api_sql_mode_quote_persiste(sql_api_client):
    client, _, _ = sql_api_client
    auth = _login(client, "kam1@akiem.com", "kam")

    r = client.post("/api/v1/catalog/quotes",
        json={"client_code": "SNCF", "client_name": "SNCF Fret"}, headers=auth)
    assert r.status_code == 200
    qid = r.json()["quote_id"]

    r = client.post(f"/api/v1/catalog/quotes/{qid}/lines",
        json={"technical_variant_code": "E186-DABNL", "country_iso": "DE",
              "duration_months": 24, "age_years": 5, "annual_mileage_km": 150_000},
        headers=auth)
    assert r.status_code == 200
    assert r.json()["calculation"]["total_monthly"] > 0

    r = client.get(f"/api/v1/catalog/quotes/{qid}", headers=auth)
    assert r.status_code == 200
    assert len(r.json()["lines"]) == 1


def test_api_sql_mode_quote_survit_a_restart(sql_api_client):
    """CRITIQUE : une quote créée reste en DB après redémarrage de l'API."""
    client, api_module, url = sql_api_client
    auth = _login(client, "kam1@akiem.com", "kam")

    r = client.post("/api/v1/catalog/quotes",
        json={"client_code": "ACME", "client_name": "ACME Corp"}, headers=auth)
    qid = r.json()["quote_id"]
    quote_number = r.json()["quote_number"]

    # Simule un restart : reload le module api, nouveau TestClient
    importlib.reload(api_module)
    client2 = TestClient(api_module.app)
    auth2 = _login(client2, "kam1@akiem.com", "kam")

    # La quote doit toujours exister
    r = client2.get(f"/api/v1/catalog/quotes/{qid}", headers=auth2)
    assert r.status_code == 200
    assert r.json()["quote"]["quote_number"] == quote_number


def test_api_sql_mode_catalog_survit_a_restart(sql_api_client):
    """Idem catalog : le seed n'est pas réappliqué, on garde ce qu'il y
    avait."""
    client, api_module, _ = sql_api_client
    # Premier appel : catalog peuplé par le seed au build
    r1 = client.get("/api/v1/catalog/manufacturers")
    nb_avant = len(r1.json())
    assert nb_avant > 0

    # Restart
    importlib.reload(api_module)
    client2 = TestClient(api_module.app)
    r2 = client2.get("/api/v1/catalog/manufacturers")
    nb_apres = len(r2.json())
    assert nb_apres == nb_avant, "Le catalog doit être persisté, pas réseedé"
