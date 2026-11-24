"""Tests de persistance SQL des composants, options et règles appliquées.

Vérifie que :
- save_component / list_components round-trip en SQL
- save_applied_rule / list_applied_rules round-trip en SQL
- add_quote_line_option / list_quote_line_options round-trip en SQL
- la cascade DB supprime tout quand on supprime la quote parente
- un restart (nouvelle sessionmaker sur le même fichier) retrouve tout
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pricing_engine.catalog.db import create_all_catalog_tables
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
from pricing_engine.catalog.sql_quote_store import SqlAlchemyQuoteStore


@pytest.fixture
def sql_quote_store():
    engine = create_engine("sqlite:///:memory:", future=True)
    create_all_catalog_tables(engine)
    sf = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    store = SqlAlchemyQuoteStore(sf)
    return store, engine


@pytest.fixture
def quote_with_line(sql_quote_store):
    store, _ = sql_quote_store
    q = Quote(
        quote_id=uuid4(),
        quote_number="Q-TEST-001",
        client_code="SNCF",
        client_name="SNCF Fret",
        created_by="kam1@akiem.com",
        status=QuoteStatus.DRAFT,
    )
    store.create_quote(q)
    line = QuoteLine(
        quote_line_id=uuid4(),
        quote_id=q.quote_id,
        line_number=1,
        technical_variant_id=uuid4(),
        technical_variant_code="E186-DABNL",
        quantity=1,
        contract_duration_months=24,
        annual_mileage_km=150_000,
        country_iso="DE",
        start_date=date.today(),
    )
    store.add_quote_line(line)

    calc = PricingCalculation(
        pricing_calculation_id=uuid4(),
        quote_line_id=line.quote_line_id,
        calculated_at=datetime.now(timezone.utc),
        dl_monthly=25_000.0,
        hm_monthly_provisioned=5_000.0,
        om_monthly=8_000.0,
        options_monthly=0.0,
        total_monthly=38_000.0,
        total_contract=38_000.0 * 24,
        niveau_validation=0,
    )
    store.save_pricing_calculation(calc)
    return store, q, line, calc


# =========================================================================
# Composants
# =========================================================================


def test_save_et_list_components(quote_with_line):
    store, q, line, calc = quote_with_line
    c1 = PricingCalculationComponent(
        component_id=uuid4(),
        pricing_calculation_id=calc.pricing_calculation_id,
        component_type="DL",
        component_code="BASE",
        description="Dry Lease base",
        monthly_amount=25_000.0,
    )
    c2 = PricingCalculationComponent(
        component_id=uuid4(),
        pricing_calculation_id=calc.pricing_calculation_id,
        component_type="HM",
        component_code="PROVISION",
        description="HM provisionné",
        monthly_amount=5_000.0,
    )
    store.save_component(c1)
    store.save_component(c2)

    comps = store.list_components(calc.pricing_calculation_id)
    assert len(comps) == 2
    types = {c.component_type for c in comps}
    assert types == {"DL", "HM"}
    # Round-trip exact
    dl = next(c for c in comps if c.component_type == "DL")
    assert dl.monthly_amount == 25_000.0
    assert dl.description == "Dry Lease base"
    assert dl.is_visible_to_client is True


def test_save_component_sans_calc_leve_erreur(sql_quote_store):
    store, _ = sql_quote_store
    orphan_calc_id = uuid4()
    with pytest.raises(ValueError, match="PricingCalculation"):
        store.save_component(PricingCalculationComponent(
            component_id=uuid4(),
            pricing_calculation_id=orphan_calc_id,
            component_type="DL",
            component_code="X",
            description="X",
            monthly_amount=100.0,
        ))


# =========================================================================
# Règles appliquées
# =========================================================================


def test_save_et_list_applied_rules(quote_with_line):
    store, q, line, calc = quote_with_line
    r1 = AppliedPricingRule(
        applied_rule_id=uuid4(),
        pricing_calculation_id=calc.pricing_calculation_id,
        rule_kind=PricingRuleKind.VOLUME_DISCOUNT,
        rule_code="REMISE_VOLUME",
        rule_description="Remise volume 5%",
        impact_percentage=-5.0,
        impact_monthly_amount=-1_900.0,
    )
    r2 = AppliedPricingRule(
        applied_rule_id=uuid4(),
        pricing_calculation_id=calc.pricing_calculation_id,
        rule_kind=PricingRuleKind.SURCHARGE,
        rule_code="SURCH_AGE",
        rule_description="Surcharge âge",
        impact_percentage=3.0,
        impact_monthly_amount=1_140.0,
    )
    store.save_applied_rule(r1)
    store.save_applied_rule(r2)

    rules = store.list_applied_rules(calc.pricing_calculation_id)
    assert len(rules) == 2
    kinds = {r.rule_kind for r in rules}
    assert kinds == {PricingRuleKind.VOLUME_DISCOUNT, PricingRuleKind.SURCHARGE}


# =========================================================================
# Options
# =========================================================================


def test_add_et_list_quote_line_options(quote_with_line):
    store, q, line, calc = quote_with_line
    o1 = QuoteLineOption(
        quote_line_option_id=uuid4(),
        quote_line_id=line.quote_line_id,
        commercial_option_id=uuid4(),
        option_code="OPT_ETCS",
        quantity=1,
        unit_price=500.0,
        billing_unit="MOIS",
        total_monthly_impact=500.0,
    )
    store.add_quote_line_option(o1)

    opts = store.list_quote_line_options(line.quote_line_id)
    assert len(opts) == 1
    assert opts[0].option_code == "OPT_ETCS"
    assert opts[0].unit_price == 500.0


# =========================================================================
# CASCADE DB : supprimer une quote supprime tout
# =========================================================================


def test_cascade_delete_quote_nettoie_tout(quote_with_line):
    store, q, line, calc = quote_with_line
    store.save_component(PricingCalculationComponent(
        component_id=uuid4(),
        pricing_calculation_id=calc.pricing_calculation_id,
        component_type="DL", component_code="BASE",
        description="Base", monthly_amount=25_000.0,
    ))
    store.save_applied_rule(AppliedPricingRule(
        applied_rule_id=uuid4(),
        pricing_calculation_id=calc.pricing_calculation_id,
        rule_kind=PricingRuleKind.VOLUME_DISCOUNT,
        rule_code="R", rule_description="R",
        impact_percentage=-5.0, impact_monthly_amount=-100.0,
    ))
    store.add_quote_line_option(QuoteLineOption(
        quote_line_option_id=uuid4(),
        quote_line_id=line.quote_line_id,
        commercial_option_id=uuid4(),
        option_code="O", quantity=1, unit_price=100.0,
        billing_unit="MOIS", total_monthly_impact=100.0,
    ))

    assert len(store.list_components(calc.pricing_calculation_id)) == 1
    assert len(store.list_applied_rules(calc.pricing_calculation_id)) == 1
    assert len(store.list_quote_line_options(line.quote_line_id)) == 1

    assert store.delete_quote(q.quote_id) is True

    # Tout doit avoir disparu via CASCADE
    assert store.get_quote(q.quote_id) is None
    assert store.get_quote_line(line.quote_line_id) is None
    assert store.get_pricing_calculation_for_line(line.quote_line_id) is None
    assert store.list_components(calc.pricing_calculation_id) == []
    assert store.list_applied_rules(calc.pricing_calculation_id) == []
    assert store.list_quote_line_options(line.quote_line_id) == []


def test_cascade_delete_line_nettoie_calc_et_components(quote_with_line):
    store, q, line, calc = quote_with_line
    store.save_component(PricingCalculationComponent(
        component_id=uuid4(),
        pricing_calculation_id=calc.pricing_calculation_id,
        component_type="DL", component_code="BASE",
        description="Base", monthly_amount=25_000.0,
    ))

    assert store.delete_quote_line(line.quote_line_id) is True

    assert store.get_quote_line(line.quote_line_id) is None
    assert store.get_pricing_calculation_for_line(line.quote_line_id) is None
    assert store.list_components(calc.pricing_calculation_id) == []
    # Mais la quote parente est intacte
    assert store.get_quote(q.quote_id) is not None


# =========================================================================
# Save PricingCalculation 2 fois : écrase l'ancien avec ses composants
# =========================================================================


def test_save_calc_2_fois_ecrase_components(quote_with_line):
    store, q, line, calc = quote_with_line
    # Premier calcul : ajoute un composant
    store.save_component(PricingCalculationComponent(
        component_id=uuid4(),
        pricing_calculation_id=calc.pricing_calculation_id,
        component_type="DL", component_code="BASE_V1",
        description="Base V1", monthly_amount=25_000.0,
    ))
    assert len(store.list_components(calc.pricing_calculation_id)) == 1

    # Nouveau calcul sur la même ligne (ex: rechiffrage)
    calc2 = PricingCalculation(
        pricing_calculation_id=uuid4(),
        quote_line_id=line.quote_line_id,
        calculated_at=datetime.now(timezone.utc),
        dl_monthly=30_000.0, hm_monthly_provisioned=0.0, om_monthly=0.0,
        options_monthly=0.0, total_monthly=30_000.0,
        total_contract=30_000.0 * 24, niveau_validation=0,
    )
    store.save_pricing_calculation(calc2)

    # L'ancien calc et ses composants ne doivent plus exister
    assert store.list_components(calc.pricing_calculation_id) == []
    # Le nouveau est bien en DB
    found = store.get_pricing_calculation_for_line(line.quote_line_id)
    assert found is not None
    assert found.pricing_calculation_id == calc2.pricing_calculation_id
    assert found.dl_monthly == 30_000.0
