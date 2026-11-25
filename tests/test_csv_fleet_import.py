"""Tests de l'import CSV de la flotte Akiem."""

from __future__ import annotations

import pytest

from pricing_engine.catalog.csv_fleet_import import (
    ImportFleetResult,
    import_fleet_csv,
)
from pricing_engine.catalog.seed import seed_catalog_akiem
from pricing_engine.catalog.seed_lot2 import seed_lot2
from pricing_engine.catalog.seed_lot3 import seed_lot3
from pricing_engine.catalog.seed_lot5 import seed_lot5
from pricing_engine.catalog.store import InMemoryCatalogStore


CSV_HEADER = (
    "asset_number,vehicle_registration_number,technical_variant_code,"
    "manufacturing_year,commissioning_date,ownership_status,"
    "operational_status,current_mileage_km,current_engine_hours,"
    "current_country_iso,current_ecm_provider_code,notes\n"
)


@pytest.fixture
def store():
    s = InMemoryCatalogStore()
    seed_catalog_akiem(s)
    seed_lot2(s)
    seed_lot3(s)
    seed_lot5(s)
    return s


# =========================================================================
# Validation du header
# =========================================================================


def test_header_manquant_rejete(store):
    csv = "asset_number,wrong\nAK-X,foo\n"
    r = import_fleet_csv(csv, store)
    assert r.errors
    assert "Colonnes manquantes" in r.errors[0]
    assert r.valid_rows == 0


def test_bom_utf8_supprime(store):
    csv = "﻿" + CSV_HEADER + (
        "AK-00900,UIC-900,193-DABNL,2020,2020-01-15,owned,available,100000,0,DE,,\n"
    )
    r = import_fleet_csv(csv, store)
    assert r.valid_rows == 1
    assert r.rejected_rows == 0


def test_separateur_point_virgule_detecte(store):
    """Excel français exporte avec ;"""
    csv = CSV_HEADER.replace(",", ";") + (
        "AK-00900;UIC-900;193-DABNL;2020;2020-01-15;owned;available;100000;0;DE;;\n"
    )
    r = import_fleet_csv(csv, store)
    assert r.valid_rows == 1


# =========================================================================
# Validation ligne à ligne
# =========================================================================


def test_asset_number_vide_rejete(store):
    csv = CSV_HEADER + ",UIC-X,193-DABNL,2020,2020-01-15,owned,available,0,0,,,\n"
    r = import_fleet_csv(csv, store)
    assert r.rejected_rows == 1
    assert any("asset_number" in e for e in r.errors)


def test_date_invalide_rejete(store):
    csv = CSV_HEADER + (
        "AK-X,UIC-X,193-DABNL,2020,15/01/2020,owned,available,0,0,,,\n"
    )
    r = import_fleet_csv(csv, store)
    assert r.rejected_rows == 1
    assert any("commissioning_date" in e for e in r.errors)


def test_manufacturing_year_hors_bornes_rejete(store):
    csv = CSV_HEADER + (
        "AK-X,UIC-X,193-DABNL,1800,2020-01-15,owned,available,0,0,,,\n"
    )
    r = import_fleet_csv(csv, store)
    assert r.rejected_rows == 1
    assert any("manufacturing_year hors bornes" in e for e in r.errors)


def test_mileage_negatif_rejete(store):
    csv = CSV_HEADER + (
        "AK-X,UIC-X,193-DABNL,2020,2020-01-15,owned,available,-100,0,,,\n"
    )
    r = import_fleet_csv(csv, store)
    assert r.rejected_rows == 1
    assert any("current_mileage_km doit être" in e for e in r.errors)


def test_ownership_status_invalide_rejete(store):
    csv = CSV_HEADER + (
        "AK-X,UIC-X,193-DABNL,2020,2020-01-15,sold,available,0,0,,,\n"
    )
    r = import_fleet_csv(csv, store)
    assert r.rejected_rows == 1
    assert any("ownership_status invalide" in e for e in r.errors)


def test_country_iso_longueur_invalide_rejete(store):
    csv = CSV_HEADER + (
        "AK-X,UIC-X,193-DABNL,2020,2020-01-15,owned,available,0,0,DEU,,\n"
    )
    r = import_fleet_csv(csv, store)
    assert r.rejected_rows == 1
    assert any("current_country_iso doit faire 2" in e for e in r.errors)


# =========================================================================
# Résolution des FK (codes → UUID catalog)
# =========================================================================


def test_variant_code_inconnu_rejete(store):
    csv = CSV_HEADER + (
        "AK-X,UIC-X,INEXISTANT-123,2020,2020-01-15,owned,available,0,0,,,\n"
    )
    r = import_fleet_csv(csv, store)
    assert r.rejected_rows == 1
    assert any("technical_variant_code inconnu" in e for e in r.errors)


def test_country_iso_inconnu_rejete(store):
    csv = CSV_HEADER + (
        "AK-X,UIC-X,193-DABNL,2020,2020-01-15,owned,available,0,0,XX,,\n"
    )
    r = import_fleet_csv(csv, store)
    assert r.rejected_rows == 1
    assert any("current_country_iso inconnu" in e for e in r.errors)


def test_ecm_provider_inconnu_rejete(store):
    csv = CSV_HEADER + (
        "AK-X,UIC-X,193-DABNL,2020,2020-01-15,owned,available,0,0,,INEXISTANT,\n"
    )
    r = import_fleet_csv(csv, store)
    assert r.rejected_rows == 1
    assert any("current_ecm_provider_code inconnu" in e for e in r.errors)


# =========================================================================
# Dry-run vs apply
# =========================================================================


def test_dry_run_n_ecrit_rien(store):
    csv = CSV_HEADER + (
        "AK-NEW,UIC-NEW,193-DABNL,2020,2020-01-15,owned,available,0,0,,,\n"
    )
    nb_avant = len(store.list_fleet_assets())
    r = import_fleet_csv(csv, store, dry_run=True)
    assert r.dry_run is True
    assert r.valid_rows == 1
    assert len(store.list_fleet_assets()) == nb_avant
    assert store.get_fleet_asset_by_asset_number("AK-NEW") is None


def test_apply_ecrit_en_store(store):
    csv = CSV_HEADER + (
        "AK-NEW,UIC-NEW,193-DABNL,2020,2020-01-15,owned,available,0,0,,,\n"
    )
    r = import_fleet_csv(csv, store, dry_run=False)
    assert r.applied is True
    assert r.inserted == 1
    assert r.updated == 0
    assert store.get_fleet_asset_by_asset_number("AK-NEW") is not None


def test_apply_bloque_si_des_lignes_rejetees(store):
    csv = CSV_HEADER + (
        "AK-OK,UIC-OK,193-DABNL,2020,2020-01-15,owned,available,0,0,,,\n"
        "AK-KO,UIC-KO,INEXISTANT,2020,2020-01-15,owned,available,0,0,,,\n"
    )
    nb_avant = len(store.list_fleet_assets())
    r = import_fleet_csv(csv, store, dry_run=False)
    # Fail-fast : on n'applique RIEN si une ligne échoue
    assert r.applied is False
    assert r.rejected_rows == 1
    assert len(store.list_fleet_assets()) == nb_avant
    assert store.get_fleet_asset_by_asset_number("AK-OK") is None


def test_idempotent_reimport_met_a_jour(store):
    csv = CSV_HEADER + (
        "AK-UPD,UIC-UPD,193-DABNL,2020,2020-01-15,owned,available,100000,0,,,V1\n"
    )
    r = import_fleet_csv(csv, store, dry_run=False)
    assert r.inserted == 1

    # Réimport avec notes modifiées
    csv2 = CSV_HEADER + (
        "AK-UPD,UIC-UPD,193-DABNL,2020,2020-01-15,owned,available,150000,0,,,V2\n"
    )
    r2 = import_fleet_csv(csv2, store, dry_run=False)
    assert r2.inserted == 0
    assert r2.updated == 1
    asset = store.get_fleet_asset_by_asset_number("AK-UPD")
    assert asset.notes == "V2"
    assert asset.current_mileage_km == 150000


# =========================================================================
# Summary() rendable
# =========================================================================


def test_summary_affiche_mode_et_compteurs(store):
    csv = CSV_HEADER + (
        "AK-SUM,UIC-SUM,193-DABNL,2020,2020-01-15,owned,available,0,0,,,\n"
    )
    r = import_fleet_csv(csv, store, dry_run=True)
    txt = r.summary()
    assert "DRY-RUN" in txt
    assert "Lignes valides:    1" in txt


def test_summary_tronque_erreurs_si_trop_nombreuses(store):
    # Genere 60 lignes fausses pour tester le tronquage à 50
    body = "".join(
        f"AK-{i:05d},UIC-{i},INEXISTANT,2020,2020-01-15,owned,available,0,0,,,\n"
        for i in range(60)
    )
    r = import_fleet_csv(CSV_HEADER + body, store, dry_run=True)
    txt = r.summary()
    assert "et 10 autres" in txt
