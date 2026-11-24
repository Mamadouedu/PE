"""Tests du soft delete FleetAsset.

Couvre :
- InMemoryCatalogStore : soft_delete, restore, filtrage par défaut,
  include_deleted
- SqlAlchemyCatalogStore : même contrat SQL, FK CASCADE préservée côté
  historique (un asset soft-deleted garde ses relevés et son historique
  maintenance)
- API : DELETE /fleet-assets/{id}, POST /fleet-assets/{id}/restore,
  audit log, permissions
"""

from __future__ import annotations

import importlib
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pricing_engine.catalog.db import create_all_catalog_tables
from pricing_engine.catalog.fleet import AssetMeterReading
from pricing_engine.catalog.seed import seed_catalog_akiem
from pricing_engine.catalog.seed_lot2 import seed_lot2
from pricing_engine.catalog.seed_lot3 import seed_lot3
from pricing_engine.catalog.seed_lot5 import seed_lot5
from pricing_engine.catalog.sql_store import SqlAlchemyCatalogStore
from pricing_engine.catalog.store import InMemoryCatalogStore


# =========================================================================
# InMemoryCatalogStore
# =========================================================================


@pytest.fixture
def inmem_store():
    s = InMemoryCatalogStore()
    seed_catalog_akiem(s)
    seed_lot2(s)
    seed_lot3(s)
    seed_lot5(s)
    return s


def test_inmem_soft_delete_masque_de_la_liste(inmem_store):
    asset = inmem_store.get_fleet_asset_by_asset_number("AK-00201")
    total_avant = len(inmem_store.list_fleet_assets())

    assert inmem_store.soft_delete_fleet_asset(asset.fleet_asset_id, "admin@akiem.com") is True

    # Masqué du listing par défaut
    assert len(inmem_store.list_fleet_assets()) == total_avant - 1
    # get_fleet_asset renvoie None par défaut
    assert inmem_store.get_fleet_asset(asset.fleet_asset_id) is None
    assert inmem_store.get_fleet_asset_by_asset_number("AK-00201") is None

    # Mais include_deleted=True le retrouve
    found = inmem_store.get_fleet_asset(asset.fleet_asset_id, include_deleted=True)
    assert found is not None
    assert found.is_deleted
    assert found.deleted_by == "admin@akiem.com"


def test_inmem_soft_delete_deux_fois_renvoie_false(inmem_store):
    asset = inmem_store.get_fleet_asset_by_asset_number("AK-00201")
    assert inmem_store.soft_delete_fleet_asset(asset.fleet_asset_id, "a@x.com") is True
    assert inmem_store.soft_delete_fleet_asset(asset.fleet_asset_id, "a@x.com") is False


def test_inmem_restore_apres_soft_delete(inmem_store):
    asset = inmem_store.get_fleet_asset_by_asset_number("AK-00201")
    inmem_store.soft_delete_fleet_asset(asset.fleet_asset_id, "admin@akiem.com")

    assert inmem_store.restore_fleet_asset(asset.fleet_asset_id) is True

    # Réapparait dans le listing standard
    assert inmem_store.get_fleet_asset(asset.fleet_asset_id) is not None
    restored = inmem_store.get_fleet_asset(asset.fleet_asset_id)
    assert not restored.is_deleted
    assert restored.deleted_by is None


def test_inmem_restore_si_pas_delete_renvoie_false(inmem_store):
    asset = inmem_store.get_fleet_asset_by_asset_number("AK-00201")
    assert inmem_store.restore_fleet_asset(asset.fleet_asset_id) is False


# =========================================================================
# SqlAlchemyCatalogStore
# =========================================================================


@pytest.fixture
def sql_store():
    engine = create_engine("sqlite:///:memory:", future=True)
    create_all_catalog_tables(engine)
    sf = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    store = SqlAlchemyCatalogStore(sf)
    seed_catalog_akiem(store)
    seed_lot2(store)
    seed_lot3(store)
    seed_lot5(store)
    return store


def test_sql_soft_delete_masque_de_la_liste(sql_store):
    asset = sql_store.get_fleet_asset_by_asset_number("AK-00201")
    total_avant = len(sql_store.list_fleet_assets())

    assert sql_store.soft_delete_fleet_asset(asset.fleet_asset_id, "admin@akiem.com") is True

    assert len(sql_store.list_fleet_assets()) == total_avant - 1
    assert sql_store.get_fleet_asset(asset.fleet_asset_id) is None
    found = sql_store.get_fleet_asset(asset.fleet_asset_id, include_deleted=True)
    assert found is not None
    assert found.is_deleted
    assert found.deleted_by == "admin@akiem.com"
    assert found.deleted_at is not None


def test_sql_soft_delete_preserve_historique(sql_store):
    """CRITIQUE : un soft delete ne doit pas détruire les relevés
    compteur et l'historique maintenance (vs un hard delete qui CASCADE
    tout). C'est tout l'intérêt du soft delete : garder l'audit."""
    asset = sql_store.get_fleet_asset_by_asset_number("AK-00201")

    # Ajoute un relevé compteur
    sql_store.add_meter_reading(AssetMeterReading(
        fleet_asset_id=asset.fleet_asset_id,
        reading_date=date.today(),
        mileage_km=asset.current_mileage_km + 50_000,
    ))
    readings_avant = sql_store.list_meter_readings(asset.fleet_asset_id)
    assert len(readings_avant) >= 1

    # Soft delete
    sql_store.soft_delete_fleet_asset(asset.fleet_asset_id, "admin@akiem.com")

    # Les relevés sont toujours là (pas de CASCADE puisque pas de DELETE)
    readings_apres = sql_store.list_meter_readings(asset.fleet_asset_id)
    assert len(readings_apres) == len(readings_avant)


def test_sql_restore(sql_store):
    asset = sql_store.get_fleet_asset_by_asset_number("AK-00201")
    sql_store.soft_delete_fleet_asset(asset.fleet_asset_id, "admin@akiem.com")

    assert sql_store.restore_fleet_asset(asset.fleet_asset_id) is True

    restored = sql_store.get_fleet_asset(asset.fleet_asset_id)
    assert restored is not None
    assert not restored.is_deleted
    assert restored.deleted_by is None


# =========================================================================
# API — endpoints
# =========================================================================


@pytest.fixture
def client():
    from pricing_engine import api as api_module
    importlib.reload(api_module)
    return TestClient(api_module.app)


def _login(client, email, mdp):
    r = client.post("/api/v1/auth/login", json={"email": email, "mot_de_passe": mdp})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_api_delete_fleet_asset_admin_seul(client):
    auth_admin = _login(client, "admin@akiem.com", "admin")
    auth_kam = _login(client, "kam1@akiem.com", "kam")

    r = client.get("/api/v1/catalog/fleet-assets", headers=auth_admin)
    aid = r.json()[0]["fleet_asset_id"]

    # KAM : refusé (pas admin_referentiel)
    r = client.delete(f"/api/v1/catalog/fleet-assets/{aid}", headers=auth_kam)
    assert r.status_code == 403

    # Admin : OK
    r = client.delete(f"/api/v1/catalog/fleet-assets/{aid}", headers=auth_admin)
    assert r.status_code == 204

    # N'apparait plus dans la liste
    r = client.get("/api/v1/catalog/fleet-assets", headers=auth_admin)
    assert aid not in {a["fleet_asset_id"] for a in r.json()}

    # Mais visible avec include_deleted=true
    r = client.get("/api/v1/catalog/fleet-assets?include_deleted=true", headers=auth_admin)
    assert aid in {a["fleet_asset_id"] for a in r.json()}


def test_api_delete_puis_restore(client):
    auth = _login(client, "admin@akiem.com", "admin")
    r = client.get("/api/v1/catalog/fleet-assets", headers=auth)
    aid = r.json()[0]["fleet_asset_id"]

    assert client.delete(f"/api/v1/catalog/fleet-assets/{aid}", headers=auth).status_code == 204
    # 2e delete : 409 (déjà supprimé)
    assert client.delete(f"/api/v1/catalog/fleet-assets/{aid}", headers=auth).status_code == 409

    # Restore
    r = client.post(f"/api/v1/catalog/fleet-assets/{aid}/restore", headers=auth)
    assert r.status_code == 200
    assert r.json()["fleet_asset_id"] == aid

    # Réapparait dans la liste normale
    r = client.get("/api/v1/catalog/fleet-assets", headers=auth)
    assert aid in {a["fleet_asset_id"] for a in r.json()}


def test_api_restore_asset_pas_supprime_renvoie_409(client):
    auth = _login(client, "admin@akiem.com", "admin")
    r = client.get("/api/v1/catalog/fleet-assets", headers=auth)
    aid = r.json()[0]["fleet_asset_id"]

    r = client.post(f"/api/v1/catalog/fleet-assets/{aid}/restore", headers=auth)
    assert r.status_code == 409


def test_api_delete_est_audite(client):
    auth = _login(client, "admin@akiem.com", "admin")
    r = client.get("/api/v1/catalog/fleet-assets", headers=auth)
    aid = r.json()[0]["fleet_asset_id"]
    asset_number = r.json()[0]["asset_number"]

    client.delete(f"/api/v1/catalog/fleet-assets/{aid}", headers=auth)

    # L'audit doit avoir enregistré l'action
    r = client.get(
        f"/api/v1/audit?action=DELETE&entity_type=FleetAsset&entity_id={aid}",
        headers=auth,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["actor_email"] == "admin@akiem.com"
    assert data[0]["details"]["asset_number"] == asset_number
