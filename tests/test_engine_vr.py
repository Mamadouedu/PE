"""Valeur résiduelle — section 6.2 :

VR(a, k) = max(VN·p, VN·(1-(1-v)·min(1, a/L)) + b8 + b16 - m·max(0, k - K_ref·a))
"""

import pytest

from conftest import SERIE_VECTRON
from pricing_engine.engine import calculer_valeur_residuelle
from pricing_engine.models import Parametres

PARAMS = Parametres()


def test_vr_sans_exces_de_km_ni_hm_realisee():
    vr = calculer_valeur_residuelle(SERIE_VECTRON, PARAMS, age_ans=5, km_cumules=600_000, hm_8_realisee=False, hm_16_realisee=False)
    attendu = SERIE_VECTRON.valeur_neuve * (1 - (1 - 0.10) * (5 / 30))
    assert vr == pytest.approx(attendu)
    assert vr == pytest.approx(1_700_000.0)


def test_vr_penalisee_par_le_depassement_de_kilometrage():
    # Même âge, mais 500 000 km au-delà du kilométrage de référence cumulé.
    sans_exces = calculer_valeur_residuelle(
        SERIE_VECTRON, PARAMS, age_ans=5, km_cumules=600_000, hm_8_realisee=False, hm_16_realisee=False
    )
    avec_exces = calculer_valeur_residuelle(
        SERIE_VECTRON, PARAMS, age_ans=5, km_cumules=1_100_000, hm_8_realisee=False, hm_16_realisee=False
    )
    assert sans_exces - avec_exces == pytest.approx(500_000 * PARAMS.perte_valeur_par_km_hors_reference)


def test_vr_ne_descend_jamais_sous_le_plancher():
    vr = calculer_valeur_residuelle(
        SERIE_VECTRON, PARAMS, age_ans=30, km_cumules=4_100_000, hm_8_realisee=False, hm_16_realisee=False
    )
    assert vr == pytest.approx(SERIE_VECTRON.valeur_neuve * PARAMS.plancher_vr_taux)


def test_bonus_hm_realisee_augmente_la_vr():
    sans_bonus = calculer_valeur_residuelle(
        SERIE_VECTRON, PARAMS, age_ans=8, km_cumules=960_000, hm_8_realisee=False, hm_16_realisee=False
    )
    avec_bonus_8 = calculer_valeur_residuelle(
        SERIE_VECTRON, PARAMS, age_ans=8, km_cumules=960_000, hm_8_realisee=True, hm_16_realisee=False
    )
    assert avec_bonus_8 - sans_bonus == pytest.approx(
        PARAMS.bonus_vr_hm8 * SERIE_VECTRON.valeur_neuve
    )
