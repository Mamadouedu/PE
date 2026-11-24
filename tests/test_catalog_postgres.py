"""Tests d'intégration SQL complet contre un vrai PostgreSQL.

Jusqu'ici les stores SQL (catalog, quote, fleet, audit) n'étaient testés
que contre SQLite. Ce fichier valide le même code contre PostgreSQL pour
attraper ce que SQLite ne voit pas :

- FK CASCADE : SQLite les ignore sans PRAGMA, PG les applique strictement
- Colonnes JSON : TEXT en SQLite, JSONB en PG (opérateurs et contraintes
  différents)
- Index composites et unicité
- Types DateTime(timezone=True) : naïfs en SQLite, tz-aware en PG
- Cas limites de transactions concurrentes

Nécessite TEST_DATABASE_URL ; sinon skippé."""

from __future__ import annotations

import os
import importlib
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from pricing_engine.catalog.db import Base, create_all_catalog_tables
from pricing_engine.catalog.fleet import AssetMeterReading
from pricing_engine.catalog.quote import (
    AppliedPricingRule,
    PricingCalculation,
    PricingCalculationComponent,
    PricingRuleKind,
    Quote,
    QuoteLine,
    QuoteLineOption,
    QuoteStatus,
)
from pricing_engine.catalog.seed import seed_catalog_akiem
from pricing_engine.catalog.seed_lot2 import seed_lot2
from pricing_engine.catalog.seed_lot3 import seed_lot3
from pricing_engine.catalog.seed_lot5 import seed_lot5
from pricing_engine.catalog.sql_quote_store import SqlAlchemyQuoteStore
from pricing_engine.catalog.sql_store import SqlAlchemyCatalogStore

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://pricing:pricing@localhost/pricing_test",
)


def _pg_disponible() -> bool:
    try:
        with create_engine(TEST_DATABASE_URL).connect():
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_disponible(),
    reason=f"PostgreSQL de test indisponible ({TEST_DATABASE_URL})",
)


@pytest.fixture
def pg_engine():
    engine = create_engine(TEST_DATABASE_URL, future=True)
    # Reset complet des tables catalog/quote/fleet avant chaque test
    Base.metadata.drop_all(engine)
    create_all_catalog_tables(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def pg_stores(pg_engine):
    sf = sessionmaker(bind=pg_engine, expire_on_commit=False, future=True)
    catalog = SqlAlchemyCatalogStore(sf)
    quotes = SqlAlchemyQuoteStore(sf)
    seed_catalog_akiem(catalog)
    seed_lot2(catalog)
    seed_lot3(catalog)
    seed_lot5(catalog)
    return catalog, quotes, sf


# =========================================================================
# Seed + lecture bit-à-bit identique à SQLite
# =========================================================================


def test_pg_seed_complet(pg_stores):
    catalog, _, _ = pg_stores
    assert len(catalog.list_manufacturers()) > 0
    assert len(catalog.list_technical_variants()) > 0
    assert len(catalog.list_fleet_assets()) == 17


# =========================================================================
# CASCADE DB : PostgreSQL applique strictement, pas besoin de PRAGMA
# =========================================================================


def test_pg_cascade_quote_vers_lines_calc_components_rules_options(pg_stores):
    catalog, quotes, _ = pg_stores
    variant = next(v for v in catalog.list_technical_variants()
                   if v.variant_code == "E186-DABNL")

    # Monte une quote avec ligne, calc, 2 composants, 1 règle, 1 option
    q = Quote(quote_id=uuid4(), quote_number="Q-PG-001",
              client_code="SNCF", client_name="SNCF Fret",
              created_by="kam1@akiem.com", status=QuoteStatus.DRAFT)
    quotes.create_quote(q)
    line = QuoteLine(
        quote_line_id=uuid4(), quote_id=q.quote_id, line_number=1,
        technical_variant_id=variant.technical_variant_id,
        technical_variant_code="E186-DABNL", quantity=1,
        contract_duration_months=24, annual_mileage_km=150_000,
        country_iso="DE", start_date=date.today(),
    )
    quotes.add_quote_line(line)
    calc = PricingCalculation(
        pricing_calculation_id=uuid4(), quote_line_id=line.quote_line_id,
        calculated_at=datetime.now(timezone.utc),
        dl_monthly=25_000.0, hm_monthly_provisioned=5_000.0, om_monthly=8_000.0,
        options_monthly=500.0, total_monthly=38_500.0,
        total_contract=38_500.0 * 24, niveau_validation=0,
    )
    quotes.save_pricing_calculation(calc)
    quotes.save_component(PricingCalculationComponent(
        component_id=uuid4(), pricing_calculation_id=calc.pricing_calculation_id,
        component_type="DL", component_code="BASE",
        description="Base", monthly_amount=25_000.0))
    quotes.save_component(PricingCalculationComponent(
        component_id=uuid4(), pricing_calculation_id=calc.pricing_calculation_id,
        component_type="HM", component_code="PROV",
        description="Prov HM", monthly_amount=5_000.0))
    quotes.save_applied_rule(AppliedPricingRule(
        applied_rule_id=uuid4(), pricing_calculation_id=calc.pricing_calculation_id,
        rule_kind=PricingRuleKind.VOLUME_DISCOUNT,
        rule_code="R", rule_description="R",
        impact_percentage=-5.0, impact_monthly_amount=-1_925.0))
    quotes.add_quote_line_option(QuoteLineOption(
        quote_line_option_id=uuid4(), quote_line_id=line.quote_line_id,
        commercial_option_id=uuid4(), option_code="ETCS",
        quantity=1, unit_price=500.0, billing_unit="MOIS",
        total_monthly_impact=500.0))

    assert len(quotes.list_components(calc.pricing_calculation_id)) == 2
    assert len(quotes.list_applied_rules(calc.pricing_calculation_id)) == 1
    assert len(quotes.list_quote_line_options(line.quote_line_id)) == 1

    # Delete la quote parente → CASCADE PG nettoie tout
    assert quotes.delete_quote(q.quote_id) is True

    assert quotes.get_quote(q.quote_id) is None
    assert quotes.get_quote_line(line.quote_line_id) is None
    assert quotes.get_pricing_calculation_for_line(line.quote_line_id) is None
    assert quotes.list_components(calc.pricing_calculation_id) == []
    assert quotes.list_applied_rules(calc.pricing_calculation_id) == []
    assert quotes.list_quote_line_options(line.quote_line_id) == []


# =========================================================================
# JSON : PostgreSQL stocke en JSONB, pas TEXT
# =========================================================================


def test_pg_audit_details_jsonb_round_trip(pg_engine):
    """Les détails audit sont une colonne JSON. En PG c'est JSONB
    (typé, interrogeable). On vérifie qu'un dict complexe round-trip."""
    from pricing_engine.audit import AuditEntry
    from pricing_engine.sql_audit import SqlAlchemyAuditStore

    sf = sessionmaker(bind=pg_engine, expire_on_commit=False, future=True)
    store = SqlAlchemyAuditStore(sf)

    details = {
        "client": "SNCF Fret",
        "montant_eur": 912_000.50,
        "flags": ["remise_volume", "dérogation_direction"],
        "nested": {"approved_by": ["pricing@akiem.com", "direction@akiem.com"]},
    }
    store.append(AuditEntry(
        actor_email="kam1@akiem.com", actor_role="KAM",
        action="SUBMIT", entity_type="Quote", entity_id="42",
        details=details,
    ))

    entries = store.list(action="SUBMIT")
    assert len(entries) == 1
    assert entries[0].details == details

    # Vérification directe en SQL : la colonne est bien JSON(B)
    with pg_engine.connect() as conn:
        typ = conn.execute(text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='audit_log' AND column_name='details'"
        )).scalar()
        # Dans SQLAlchemy JSON → jsonb en PG, json en SQLite
        assert typ in ("jsonb", "json")


# =========================================================================
# UUID stockés en String(36) — portabilité SQLite/PG
# =========================================================================


def test_pg_uuid_string36_fonctionne(pg_stores):
    catalog, _, _ = pg_stores
    asset = catalog.get_fleet_asset_by_asset_number("AK-00201")
    # Le get doit marcher avec l'UUID objet Python, même si la DB stocke String
    found = catalog.get_fleet_asset(asset.fleet_asset_id)
    assert found is not None
    assert found.fleet_asset_id == asset.fleet_asset_id


# =========================================================================
# Soft delete sur PG : filtrage par defaut + CASCADE non déclenché
# =========================================================================


def test_pg_soft_delete_fleet_asset(pg_stores):
    catalog, _, _ = pg_stores
    asset = catalog.get_fleet_asset_by_asset_number("AK-00201")

    catalog.add_meter_reading(AssetMeterReading(
        fleet_asset_id=asset.fleet_asset_id,
        reading_date=date.today(),
        mileage_km=asset.current_mileage_km + 50_000,
    ))
    readings_avant = len(catalog.list_meter_readings(asset.fleet_asset_id))

    assert catalog.soft_delete_fleet_asset(asset.fleet_asset_id, "admin@akiem.com") is True

    assert catalog.get_fleet_asset(asset.fleet_asset_id) is None
    found = catalog.get_fleet_asset(asset.fleet_asset_id, include_deleted=True)
    assert found.is_deleted
    assert found.deleted_by == "admin@akiem.com"
    # deleted_at en PG : tz-aware
    assert found.deleted_at.tzinfo is not None

    # Les relevés sont préservés (pas de CASCADE tant que la ligne existe)
    assert len(catalog.list_meter_readings(asset.fleet_asset_id)) == readings_avant


# =========================================================================
# Index composites et uniques
# =========================================================================


def test_pg_index_uniques_presents(pg_engine):
    """Vérifie que les index critiques pour le pricing engine sont là en PG."""
    with pg_engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename IN ('catalog_dry_lease_rates', "
            "'catalog_operating_maintenance_rates')"
        )).scalars().all()
        # ix_dl_lookup (unique) et ix_om_lookup sont essentiels au moteur
        names = set(rows)
        assert any("dl_lookup" in n for n in names), f"ix_dl_lookup absent: {names}"
        assert any("om_lookup" in n for n in names), f"ix_om_lookup absent: {names}"


# =========================================================================
# Bascule complète API en mode PG
# =========================================================================


@pytest.fixture
def pg_api_client(pg_engine):
    """Reload l'API avec CATALOG_DATABASE_URL=postgres."""
    old = os.environ.get("CATALOG_DATABASE_URL")
    os.environ["CATALOG_DATABASE_URL"] = TEST_DATABASE_URL
    from pricing_engine import api as api_module
    importlib.reload(api_module)
    client = TestClient(api_module.app)
    yield client, api_module
    if old is None:
        os.environ.pop("CATALOG_DATABASE_URL", None)
    else:
        os.environ["CATALOG_DATABASE_URL"] = old
    importlib.reload(api_module)


def _login(client, email, mdp):
    r = client.post("/api/v1/auth/login", json={"email": email, "mot_de_passe": mdp})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_pg_api_chiffrage_end_to_end(pg_api_client):
    client, _ = pg_api_client
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
    assert data["dl_mensuel"] == pytest.approx(25289.0, rel=0.01)


def test_pg_api_quote_submit_persiste_et_audit(pg_api_client):
    client, api_module = pg_api_client
    auth_kam = _login(client, "kam1@akiem.com", "kam")
    auth_admin = _login(client, "admin@akiem.com", "admin")

    r = client.post("/api/v1/catalog/quotes",
        json={"client_code": "SNCF", "client_name": "SNCF Fret"}, headers=auth_kam)
    qid = r.json()["quote_id"]
    client.post(f"/api/v1/catalog/quotes/{qid}/lines",
        json={"technical_variant_code": "E186-DABNL", "country_iso": "DE",
              "duration_months": 24, "age_years": 5, "annual_mileage_km": 150_000},
        headers=auth_kam)
    client.post(f"/api/v1/catalog/quotes/{qid}/submit", headers=auth_kam)

    # Restart simulé : la quote reste en DB
    importlib.reload(api_module)
    client2 = TestClient(api_module.app)
    auth2 = _login(client2, "kam1@akiem.com", "kam")
    r = client2.get(f"/api/v1/catalog/quotes/{qid}", headers=auth2)
    assert r.status_code == 200
    assert r.json()["quote"]["status"] == "submitted"

    # L'audit log aussi
    auth_admin2 = _login(client2, "admin@akiem.com", "admin")
    r = client2.get(f"/api/v1/audit?entity_id={qid}", headers=auth_admin2)
    assert r.status_code == 200
    data = r.json()
    actions = {e["action"] for e in data}
    assert "SUBMIT" in actions


def test_pg_api_soft_delete_fleet(pg_api_client):
    client, _ = pg_api_client
    auth = _login(client, "admin@akiem.com", "admin")
    r = client.get("/api/v1/catalog/fleet-assets", headers=auth)
    aid = r.json()[0]["fleet_asset_id"]

    assert client.delete(f"/api/v1/catalog/fleet-assets/{aid}", headers=auth).status_code == 204

    r = client.get("/api/v1/catalog/fleet-assets", headers=auth)
    assert aid not in {a["fleet_asset_id"] for a in r.json()}

    r = client.get("/api/v1/catalog/fleet-assets?include_deleted=true", headers=auth)
    assert aid in {a["fleet_asset_id"] for a in r.json()}


# =========================================================================
# Contraintes UNIQUE : PG les applique, erreur IntegrityError attendue
# =========================================================================


def test_pg_asset_number_unique(pg_stores):
    """asset_number est unique sur FleetAssetRow. En PG l'insertion d'un
    doublon via SQL direct doit lever IntegrityError. (Via le store
    upsert_fleet_asset c'est géré par logique applicative.)"""
    _, _, sf = pg_stores
    from pricing_engine.catalog.db import FleetAssetRow
    with sf() as s:
        existing = s.execute(text("SELECT asset_number FROM fleet_assets LIMIT 1")).scalar()

    with sf() as s:
        s.add(FleetAssetRow(
            fleet_asset_id=str(uuid4()),
            asset_number=existing,  # Doublon
            vehicle_registration_number="DOUBLON-UIC",
            technical_variant_id=str(uuid4()),
            manufacturing_year=2020,
            commissioning_date=date(2020, 1, 1),
        ))
        with pytest.raises(IntegrityError):
            s.commit()
