"""Tests du catalogue PricingHub (Lot 1 du doc Architecture Cible)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pricing_engine.catalog.entities import (
    Country,
    Homologation,
    LocomotiveSeries,
    Manufacturer,
    ProductFamily,
    ProductPlatform,
    TechnicalVariant,
    TractionMode,
    VariantHomologation,
)
from pricing_engine.catalog.seed import seed_catalog_akiem
from pricing_engine.catalog.store import InMemoryCatalogStore


# =========================================================================
# Tests unitaires du store in-memory
# =========================================================================


def test_upsert_manufacturer_dedup_par_code():
    store = InMemoryCatalogStore()
    m1 = store.upsert_manufacturer(Manufacturer(
        code="BOMBARDIER", name="Bombardier", country_of_origin_iso="CA",
    ))
    m2 = store.upsert_manufacturer(Manufacturer(
        code="bombardier", name="Bombardier Alstom", country_of_origin_iso="CA",
    ))
    # L'ID est conservé malgré l'UUID initial différent (dédup par code)
    assert m1.manufacturer_id == m2.manufacturer_id
    assert len(store.list_manufacturers()) == 1


def test_upsert_country_normalise_iso():
    store = InMemoryCatalogStore()
    c = store.upsert_country(Country(iso_alpha2="de", name_fr="Allemagne", name_en="Germany"))
    assert c.iso_alpha2 == "DE"
    assert store.get_country_by_iso("de") is not None
    assert store.get_country_by_iso("DE") is not None


def test_platform_refuse_famille_inconnue():
    store = InMemoryCatalogStore()
    m = store.upsert_manufacturer(Manufacturer(code="SIEMENS", name="Siemens", country_of_origin_iso="DE"))
    from uuid import uuid4
    with pytest.raises(ValueError, match="ProductFamily"):
        store.upsert_product_platform(ProductPlatform(
            product_family_id=uuid4(),
            platform_code="VECTRON_MS",
            platform_name="Vectron MS",
            manufacturer_id=m.manufacturer_id,
            traction_mode=TractionMode.MS,
        ))


def test_hierarchie_famille_plateforme_serie_variante():
    store = InMemoryCatalogStore()

    m = store.upsert_manufacturer(Manufacturer(code="BOMBARDIER", name="Bombardier", country_of_origin_iso="CA"))
    f = store.upsert_product_family(ProductFamily(family_code="ELECTRIC_LOCO", family_name="Electric Locomotive"))
    p = store.upsert_product_platform(ProductPlatform(
        product_family_id=f.product_family_id,
        platform_code="TRAXX_MS", platform_name="Traxx Multi-System",
        manufacturer_id=m.manufacturer_id, traction_mode=TractionMode.MS,
    ))
    s = store.upsert_series(LocomotiveSeries(
        product_platform_id=p.product_platform_id,
        series_code="E186", series_name="E186 / F140 MS",
        nominal_power_kw=5600, maximum_speed_kmh=140, starting_tractive_effort_kn=300,
        traction_mode=TractionMode.MS,
    ))
    v = store.upsert_technical_variant(TechnicalVariant(
        series_id=s.series_id,
        variant_code="E186-DABNL", variant_name="Traxx F140 MS - DE/AT/BE/NL",
        manufacturer_model_name="TRAXX F140 MS",
        technical_configuration_code="TRAXX_MS|E186-DABNL",
    ))

    # Filtre descendant
    assert len(store.list_product_platforms(family_id=f.product_family_id)) == 1
    assert len(store.list_series(platform_id=p.product_platform_id)) == 1
    assert len(store.list_technical_variants(series_id=s.series_id)) == 1
    # Récup par code
    assert store.get_variant_by_code("e186-dabnl").technical_variant_id == v.technical_variant_id


def test_m2m_variant_homologation_et_countries():
    store = InMemoryCatalogStore()
    seed_catalog_akiem(store)

    # E186-DABNL devrait être homologuée par DABNL qui couvre 4 pays
    variant = store.get_variant_by_code("E186-DABNL")
    homos = store.list_homologations_for_variant(variant.technical_variant_id)
    assert len(homos) == 1
    assert homos[0].homologation_code == "DABNL"

    pays = store.list_countries_for_homologation(homos[0].homologation_id)
    codes = sorted(c.iso_alpha2 for c in pays)
    assert codes == ["AT", "BE", "DE", "NL"]


# =========================================================================
# Tests du seed de référence
# =========================================================================


def test_seed_catalog_akiem_cree_la_hierarchie_complete():
    store = seed_catalog_akiem()
    assert len(store.list_manufacturers()) == 5
    assert len(store.list_countries()) == 17
    assert len(store.list_product_families()) == 4
    assert len(store.list_product_platforms()) == 10
    assert len(store.list_series()) == 7
    assert len(store.list_technical_variants()) == 15
    assert len(store.list_homologations()) == 11


def test_seed_respecte_la_decision_architecturale_locomotive_ne_porte_pas_le_prix():
    """Section 16 du doc : Locomotive ≠ Prix. On vérifie qu'aucune entité
    du catalogue ne porte de champ prix (pas de monthly_base_rent, pas de
    bp_hm, etc.) — ces notions vivent exclusivement dans PriceBook (Lot 3)."""
    store = seed_catalog_akiem()
    for variant in store.list_technical_variants():
        dump = variant.model_dump()
        assert not any(k.lower().endswith("_rent") or k.startswith("price") or k.startswith("rate") for k in dump), \
            f"TechnicalVariant ne doit pas porter de prix : {dump.keys()}"


# =========================================================================
# Tests des endpoints REST
# =========================================================================


@pytest.fixture
def client():
    from pricing_engine.api import app
    return TestClient(app)


def test_get_hierarchie_tree(client):
    r = client.get("/api/v1/catalog/tree")
    assert r.status_code == 200
    tree = r.json()
    assert len(tree) == 4  # 4 familles
    # On trouve bien TRAXX_MS
    traxx_ms = None
    for family in tree:
        for platform in family["platforms"]:
            if platform["platform_code"] == "TRAXX_MS":
                traxx_ms = platform
                break
    assert traxx_ms is not None
    # TRAXX_MS contient E186, E187, E188
    series_codes = {s["series_code"] for s in traxx_ms["series"]}
    assert "E186" in series_codes
    # E186 a au moins la variante DABNL
    e186 = next(s for s in traxx_ms["series"] if s["series_code"] == "E186")
    variant_codes = {v["variant_code"] for v in e186["variants"]}
    assert "E186-DABNL" in variant_codes


def test_list_manufacturers(client):
    r = client.get("/api/v1/catalog/manufacturers")
    assert r.status_code == 200
    codes = {m["code"] for m in r.json()}
    assert {"BOMBARDIER", "ALSTOM", "SIEMENS", "STADLER", "VOSSLOH"}.issubset(codes)


def test_list_countries(client):
    r = client.get("/api/v1/catalog/countries")
    assert r.status_code == 200
    iso_codes = {c["iso_alpha2"] for c in r.json()}
    assert {"DE", "AT", "FR", "PL", "CH"}.issubset(iso_codes)


def test_list_technical_variants_filtre_par_serie(client):
    # D'abord trouver l'ID de E186
    r = client.get("/api/v1/catalog/series")
    e186 = next(s for s in r.json() if s["series_code"] == "E186")

    r = client.get(f"/api/v1/catalog/technical-variants?series_id={e186['series_id']}")
    assert r.status_code == 200
    variants = r.json()
    codes = {v["variant_code"] for v in variants}
    assert codes == {"E186-DABNL", "E186-DBF", "E186-DABF"}


def test_variant_homologations_renvoie_les_bonnes_homologations(client):
    r = client.get("/api/v1/catalog/technical-variants")
    e186_dabnl = next(v for v in r.json() if v["variant_code"] == "E186-DABNL")
    r = client.get(f"/api/v1/catalog/technical-variants/{e186_dabnl['technical_variant_id']}/homologations")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["homologation_code"] == "DABNL"
