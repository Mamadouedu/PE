"""Tests d'atomicité : les écritures multi-tables ne laissent pas d'état
partiellement cohérent en cas d'erreur."""

from __future__ import annotations

import pytest

from pricing_engine.catalog.quote_store import InMemoryQuoteStore, QuoteService
from pricing_engine.catalog.seed import seed_catalog_akiem
from pricing_engine.catalog.seed_lot2 import seed_lot2
from pricing_engine.catalog.seed_lot3 import seed_lot3
from pricing_engine.catalog.store import InMemoryCatalogStore


@pytest.fixture
def service():
    catalog = InMemoryCatalogStore()
    seed_catalog_akiem(catalog)
    seed_lot2(catalog)
    seed_lot3(catalog)
    return QuoteService(catalog, InMemoryQuoteStore())


def test_variante_inconnue_leve_avant_tout_ecriture(service):
    """Si la variante demandée n'existe pas, aucune ligne ne doit être
    créée. On vérifie en comptant les lignes de la quote avant/après."""
    q = service.creer_quote("ACME", "ACME", "kam@akiem.com")
    lignes_avant = len(service._quotes.list_quote_lines(q.quote_id))

    with pytest.raises(ValueError, match="inconnue"):
        service.ajouter_ligne_et_chiffrer(
            quote_id=q.quote_id,
            technical_variant_code="VARIANT-FANTOME",
            country_iso="DE",
            duration_months=24,
            age_years=5,
            annual_mileage_km=150_000,
        )

    assert len(service._quotes.list_quote_lines(q.quote_id)) == lignes_avant
    # La quote existe, ses totaux sont intacts
    q_apres = service._quotes.get_quote(q.quote_id)
    assert q_apres.total_mensuel == 0


def test_pays_inconnu_laisse_la_quote_propre(service):
    """Un pays sans country_group → erreur, mais aucune ligne orpheline."""
    q = service.creer_quote("ACME", "ACME", "kam@akiem.com")

    with pytest.raises(ValueError):
        service.ajouter_ligne_et_chiffrer(
            quote_id=q.quote_id,
            technical_variant_code="E186-DABNL",
            country_iso="XX",  # Pays qui n'est dans aucun country_group
            duration_months=24,
            age_years=5,
            annual_mileage_km=150_000,
        )

    assert service._quotes.list_quote_lines(q.quote_id) == []


def test_une_ligne_qui_marche_apres_une_qui_echoue(service):
    """Après un échec, on peut toujours ajouter une ligne correcte."""
    q = service.creer_quote("ACME", "ACME", "kam@akiem.com")

    with pytest.raises(ValueError):
        service.ajouter_ligne_et_chiffrer(
            quote_id=q.quote_id,
            technical_variant_code="GHOST", country_iso="DE",
            duration_months=24, age_years=5, annual_mileage_km=150_000,
        )
    # La quote est propre, aucune ligne restante
    assert service._quotes.list_quote_lines(q.quote_id) == []

    # Ajout correct → line_number = 1 (pas 2) parce qu'aucune ligne précédente
    line, calc = service.ajouter_ligne_et_chiffrer(
        quote_id=q.quote_id,
        technical_variant_code="E186-DABNL", country_iso="DE",
        duration_months=24, age_years=5, annual_mileage_km=150_000,
    )
    assert line.line_number == 1
    assert calc.total_monthly > 0


def test_totaux_quote_coherents_apres_echec(service):
    """Après un ajout échoué, les totaux de la quote restent cohérents
    avec les lignes effectivement présentes (pas de somme partielle)."""
    q = service.creer_quote("ACME", "ACME", "kam@akiem.com")
    # 1 ligne qui marche
    _, calc1 = service.ajouter_ligne_et_chiffrer(
        quote_id=q.quote_id,
        technical_variant_code="E186-DABNL", country_iso="DE",
        duration_months=24, age_years=5, annual_mileage_km=150_000,
    )
    total_apres_1 = service._quotes.get_quote(q.quote_id).total_mensuel

    # 1 ligne qui échoue → total inchangé
    with pytest.raises(ValueError):
        service.ajouter_ligne_et_chiffrer(
            quote_id=q.quote_id,
            technical_variant_code="GHOST", country_iso="DE",
            duration_months=24, age_years=5, annual_mileage_km=150_000,
        )
    total_apres_echec = service._quotes.get_quote(q.quote_id).total_mensuel
    assert total_apres_echec == total_apres_1, "Total pollué par un ajout échoué"
