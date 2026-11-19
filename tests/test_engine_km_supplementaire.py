"""Km supplémentaire — section 6.1 :

prix = (coût HM/km × coef HM + OM €/km × coef OM) × (1 + majoration)
"""

import pytest

from pricing_engine.engine import calculer_offre


def test_prix_km_supplementaire(version_publiee, config_base):
    offre = calculer_offre(version_publiee, config_base)

    cout_hm_par_km = (150_000 + 200_000) / (16 * 120_000)
    attendu = (cout_hm_par_km * 1.0 + 0.05 * 1.0) * 1.25
    assert offre.prix_km_supplementaire == pytest.approx(attendu)


def test_prix_km_supplementaire_suit_les_coefficients_de_tranche(version_publiee, config_base):
    offre_a = calculer_offre(version_publiee, config_base)
    offre_b = calculer_offre(version_publiee, config_base.model_copy(update={"km_annuel": 160_000}))

    # Tranche B : coefficients HM/OM plus élevés (1.1 / 1.05) => km supp plus cher.
    assert offre_b.prix_km_supplementaire > offre_a.prix_km_supplementaire
