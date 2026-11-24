"""Tests d'intégration du SqlAlchemyCatalogStore.

Utilise SQLite en mémoire pour la rapidité. Les mêmes tests tourneront
sur PostgreSQL en prod via la même interface SQLAlchemy.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pricing_engine.catalog.db import Base, create_all_catalog_tables
from pricing_engine.catalog.entities import (
    Country,
    Homologation,
    HomologationCountry,
    LocomotiveSeries,
    Manufacturer,
    ProductFamily,
    ProductPlatform,
    TechnicalVariant,
    TractionMode,
    VariantHomologation,
)
from pricing_engine.catalog.sql_store import SqlAlchemyCatalogStore


@pytest.fixture
def store():
    """SQLite in-memory + tables fraîches pour chaque test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    create_all_catalog_tables(engine)
    sf = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    yield SqlAlchemyCatalogStore(sf)


# =========================================================================
# Manufacturers
# =========================================================================


def test_upsert_manufacturer_et_relecture(store):
    m = store.upsert_manufacturer(Manufacturer(
        code="BOMBARDIER", name="Bombardier Transportation", country_of_origin_iso="CA",
    ))
    relu = store.get_manufacturer_by_code("bombardier")
    assert relu is not None
    assert relu.name == "Bombardier Transportation"
    assert relu.manufacturer_id == m.manufacturer_id


def test_upsert_manufacturer_dedup_par_code(store):
    m1 = store.upsert_manufacturer(Manufacturer(
        code="SIEMENS", name="Siemens", country_of_origin_iso="DE",
    ))
    # Deuxième upsert avec un UUID différent mais le même code → met à jour
    m2 = store.upsert_manufacturer(Manufacturer(
        code="SIEMENS", name="Siemens Mobility GmbH", country_of_origin_iso="DE",
    ))
    assert len(store.list_manufacturers()) == 1
    assert store.get_manufacturer_by_code("SIEMENS").name == "Siemens Mobility GmbH"


def test_list_manufacturers_tries_par_nom(store):
    for code, name in [("ZX", "Zebra"), ("AX", "Alpha"), ("MX", "Mango")]:
        store.upsert_manufacturer(Manufacturer(code=code, name=name, country_of_origin_iso="DE"))
    names = [m.name for m in store.list_manufacturers()]
    assert names == ["Alpha", "Mango", "Zebra"]


# =========================================================================
# Countries
# =========================================================================


def test_countries_normalise_iso_et_dedup(store):
    c1 = store.upsert_country(Country(iso_alpha2="de", name_fr="Allemagne", name_en="Germany"))
    assert c1.iso_alpha2 == "DE"
    # Upsert avec minuscules → même pays
    store.upsert_country(Country(iso_alpha2="DE", name_fr="Allemagne", name_en="Germany", default_network_code="DB_NETZ"))
    assert len(store.list_countries()) == 1
    assert store.get_country_by_iso("de").default_network_code == "DB_NETZ"


# =========================================================================
# Hierarchy avec FK
# =========================================================================


def test_platform_refuse_famille_inconnue(store):
    m = store.upsert_manufacturer(Manufacturer(code="S", name="S", country_of_origin_iso="DE"))
    from uuid import uuid4
    with pytest.raises(ValueError, match="ProductFamily"):
        store.upsert_product_platform(ProductPlatform(
            product_family_id=uuid4(),
            platform_code="X", platform_name="X",
            manufacturer_id=m.manufacturer_id,
            traction_mode=TractionMode.MS,
        ))


def test_hierarchie_complete_persistee(store):
    m = store.upsert_manufacturer(Manufacturer(code="BOMBARDIER", name="Bombardier", country_of_origin_iso="CA"))
    f = store.upsert_product_family(ProductFamily(family_code="ELECTRIC_LOCO", family_name="Electric Locomotive"))
    p = store.upsert_product_platform(ProductPlatform(
        product_family_id=f.product_family_id,
        platform_code="TRAXX_MS", platform_name="Traxx Multi-System",
        manufacturer_id=m.manufacturer_id, traction_mode=TractionMode.MS,
    ))
    s = store.upsert_series(LocomotiveSeries(
        product_platform_id=p.product_platform_id,
        series_code="E186", series_name="E186",
        nominal_power_kw=5600, maximum_speed_kmh=140, starting_tractive_effort_kn=300,
        traction_mode=TractionMode.MS,
    ))
    v = store.upsert_technical_variant(TechnicalVariant(
        series_id=s.series_id,
        variant_code="E186-DABNL", variant_name="Traxx F140 MS DABNL",
        manufacturer_model_name="TRAXX F140 MS",
        technical_configuration_code="TRAXX_MS|E186-DABNL",
    ))

    # Reload depuis la DB
    reread = store.get_variant_by_code("E186-DABNL")
    assert reread.variant_code == "E186-DABNL"
    assert reread.technical_variant_id == v.technical_variant_id

    # Filtres
    assert len(store.list_product_platforms(family_id=f.product_family_id)) == 1
    assert len(store.list_series(platform_id=p.product_platform_id)) == 1
    assert len(store.list_technical_variants(series_id=s.series_id)) == 1


def test_m2m_variant_homologation_round_trip(store):
    # Setup hiérarchie minimale
    m = store.upsert_manufacturer(Manufacturer(code="B", name="B", country_of_origin_iso="CA"))
    f = store.upsert_product_family(ProductFamily(family_code="EL", family_name="EL"))
    p = store.upsert_product_platform(ProductPlatform(
        product_family_id=f.product_family_id, platform_code="X", platform_name="X",
        manufacturer_id=m.manufacturer_id, traction_mode=TractionMode.MS,
    ))
    s = store.upsert_series(LocomotiveSeries(
        product_platform_id=p.product_platform_id, series_code="SX", series_name="SX",
    ))
    v = store.upsert_technical_variant(TechnicalVariant(
        series_id=s.series_id, variant_code="SX-ABC",
        variant_name="SX-ABC", manufacturer_model_name="M",
        technical_configuration_code="C",
    ))
    h1 = store.upsert_homologation(Homologation(homologation_code="DABNL", homologation_name="DABNL"))
    h2 = store.upsert_homologation(Homologation(homologation_code="DACH", homologation_name="DACH"))

    store.set_variant_homologation(VariantHomologation(
        technical_variant_id=v.technical_variant_id, homologation_id=h1.homologation_id,
    ))
    store.set_variant_homologation(VariantHomologation(
        technical_variant_id=v.technical_variant_id, homologation_id=h2.homologation_id,
    ))

    homos = store.list_homologations_for_variant(v.technical_variant_id)
    codes = {h.homologation_code for h in homos}
    assert codes == {"DABNL", "DACH"}

    # Reverse lookup
    variants = store.list_variants_for_homologation(h1.homologation_id)
    assert len(variants) == 1
    assert variants[0].variant_code == "SX-ABC"

    # Suppression du lien
    assert store.remove_variant_homologation(v.technical_variant_id, h1.homologation_id) is True
    assert len(store.list_homologations_for_variant(v.technical_variant_id)) == 1


def test_homologation_country_m2m(store):
    h = store.upsert_homologation(Homologation(homologation_code="DABNL", homologation_name="DABNL"))
    de = store.upsert_country(Country(iso_alpha2="DE", name_fr="Allemagne", name_en="Germany"))
    at = store.upsert_country(Country(iso_alpha2="AT", name_fr="Autriche", name_en="Austria"))

    store.set_homologation_country(HomologationCountry(
        homologation_id=h.homologation_id, country_id=de.country_id, network_code="DB_NETZ",
    ))
    store.set_homologation_country(HomologationCountry(
        homologation_id=h.homologation_id, country_id=at.country_id, network_code="OBB",
    ))

    countries = store.list_countries_for_homologation(h.homologation_id)
    isos = sorted(c.iso_alpha2 for c in countries)
    assert isos == ["AT", "DE"]


# =========================================================================
# Isolation entre tests (SQLite :memory: → chaque test a sa DB)
# =========================================================================


def test_isolation_entre_tests():
    """Vérifie qu'un deuxième `store` a bien sa propre DB vide."""
    engine = create_engine("sqlite:///:memory:", future=True)
    create_all_catalog_tables(engine)
    sf = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    store2 = SqlAlchemyCatalogStore(sf)
    assert store2.list_manufacturers() == []
    assert store2.list_countries() == []


# =========================================================================
# Persistance effective (pas juste mémoire SQLAlchemy)
# =========================================================================


def test_persistance_survit_a_la_reconnexion(tmp_path):
    """Écrit dans un fichier SQLite, ferme la connexion, rouvre → données
    toujours là."""
    db_file = tmp_path / "test.db"
    url = f"sqlite:///{db_file}"

    engine = create_engine(url, future=True)
    create_all_catalog_tables(engine)
    sf = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    store = SqlAlchemyCatalogStore(sf)

    store.upsert_manufacturer(Manufacturer(
        code="BOMBARDIER", name="Bombardier", country_of_origin_iso="CA",
    ))
    engine.dispose()  # Ferme toutes les connexions

    # Nouveau process simulé : nouveau store
    engine2 = create_engine(url, future=True)
    sf2 = sessionmaker(bind=engine2, expire_on_commit=False, future=True)
    store2 = SqlAlchemyCatalogStore(sf2)
    assert len(store2.list_manufacturers()) == 1
    assert store2.get_manufacturer_by_code("BOMBARDIER") is not None
