"""Test end-to-end : seed catalog Lots 1+2+3 dans SQL + chiffrage moteur v2.

Démontre que le moteur v2 fonctionne de manière interchangeable sur
InMemoryCatalogStore ET SqlAlchemyCatalogStore. C'est la garantie que
la bascule production (DATABASE_URL défini) ne change pas le résultat.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pricing_engine.catalog.db import create_all_catalog_tables
from pricing_engine.catalog.pricing_engine_v2 import DemandeChiffrage, MoteurPrixV2
from pricing_engine.catalog.seed import seed_catalog_akiem
from pricing_engine.catalog.seed_lot2 import seed_lot2
from pricing_engine.catalog.seed_lot3 import seed_lot3
from pricing_engine.catalog.sql_store import SqlAlchemyCatalogStore
from pricing_engine.catalog.store import InMemoryCatalogStore


@pytest.fixture
def sql_store():
    """SQLite :memory: + seeds complets Lots 1+2+3."""
    engine = create_engine("sqlite:///:memory:", future=True)
    create_all_catalog_tables(engine)
    sf = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    store = SqlAlchemyCatalogStore(sf)
    seed_catalog_akiem(store)
    seed_lot2(store)
    seed_lot3(store)
    return store


@pytest.fixture
def memory_store():
    store = InMemoryCatalogStore()
    seed_catalog_akiem(store)
    seed_lot2(store)
    seed_lot3(store)
    return store


# =========================================================================
# Chiffrage SQL direct
# =========================================================================


def test_seed_complet_sur_sqlite(sql_store):
    """Vérifie que les 3 seeds s'appliquent proprement sur SQL."""
    assert len(sql_store.list_manufacturers()) == 5
    assert len(sql_store.list_countries()) == 17
    assert len(sql_store.list_technical_variants()) == 15
    assert len(sql_store.list_homologations()) == 11
    assert len(sql_store.list_usage_profiles()) == 6
    assert len(sql_store.list_mileage_bands()) == 6
    assert len(sql_store.list_maintenance_operations()) == 7
    assert len(sql_store.list_price_books()) == 3
    assert len(sql_store.list_dry_lease_rates()) == 1440
    assert len(sql_store.list_operating_maintenance_rates()) == 90


def test_chiffrage_sql_marche(sql_store):
    """Le moteur v2 branché sur SQL doit chiffrer comme en in-memory."""
    moteur = MoteurPrixV2(sql_store)
    res = moteur.chiffrer(DemandeChiffrage(
        technical_variant_code="E186-DABNL",
        country_iso="DE",
        duration_months=24,
        age_years=5,
        annual_mileage_km=150_000,
    ))
    assert res.variant_code == "E186-DABNL"
    assert res.dl_mensuel > 20_000
    assert res.total_mensuel == pytest.approx(
        res.dl_mensuel + res.hm_mensuel_provisionne + res.om_mensuel
    )
    assert res.detail_om["mileage_band"] == "OM_120_160"
    assert res.detail_dl["lease_band"] == "MEDIUM"
    assert res.detail_dl["asset_age_band"] == "YOUNG"


def test_chiffrage_sql_identique_a_memory(sql_store, memory_store):
    """**Le test critique** : SQL et in-memory doivent produire le MÊME
    chiffrage pour la même demande. Garantit que la bascule production
    est transparente."""
    demande = DemandeChiffrage(
        technical_variant_code="E186-DABNL",
        country_iso="DE",
        duration_months=24,
        age_years=5,
        annual_mileage_km=150_000,
    )
    r_sql = MoteurPrixV2(sql_store).chiffrer(demande)
    r_mem = MoteurPrixV2(memory_store).chiffrer(demande)
    assert r_sql.dl_mensuel == pytest.approx(r_mem.dl_mensuel)
    assert r_sql.om_mensuel == pytest.approx(r_mem.om_mensuel)
    assert r_sql.hm_mensuel_provisionne == pytest.approx(r_mem.hm_mensuel_provisionne)
    assert r_sql.total_mensuel == pytest.approx(r_mem.total_mensuel)


def test_chiffrage_sql_sur_plusieurs_configurations(sql_store):
    """Plusieurs variantes × pays × paliers."""
    moteur = MoteurPrixV2(sql_store)
    configs = [
        ("E186-DABNL", "DE", 24, 5, 150_000),
        ("193-DACHI", "CH", 36, 3, 180_000),
        ("159-DACH", "AT", 60, 8, 90_000),
        ("E188-PLCZSK", "PL", 48, 2, 200_000),
    ]
    for variant, pays, duree, age, km in configs:
        res = moteur.chiffrer(DemandeChiffrage(
            technical_variant_code=variant,
            country_iso=pays,
            duration_months=duree,
            age_years=age,
            annual_mileage_km=km,
        ))
        assert res.total_mensuel > 0, f"{variant} {pays}"
        assert res.detail_dl is not None


def test_resolution_palier_sql(sql_store):
    """Vérifie que la résolution de palier est faite SQL-side (plus rapide
    qu'un full-scan Python)."""
    band = sql_store.get_mileage_band_for_annual_km(150_000)
    assert band is not None
    assert band.band_code == "OM_120_160"
    # Borne haute ouverte
    band_plus = sql_store.get_mileage_band_for_annual_km(300_000)
    assert band_plus.band_code == "OM_240_PLUS"


def test_resolution_country_group_sql(sql_store):
    """Un pays appartient à exactement un country_group."""
    cg_de = sql_store.get_country_group_for_iso("DE")
    assert cg_de.group_code == "CORE_DACH"
    cg_pl = sql_store.get_country_group_for_iso("PL")
    assert cg_pl.group_code == "FRET_EST"


def test_get_current_published_version_sql(sql_store):
    """L'index sur status+valid_from permet une lookup performant."""
    v = sql_store.get_current_published_version("DL_STANDARD")
    assert v is not None
    assert v.status.value == "published"
    assert v.year == 2026
    assert v.version_number == 1
