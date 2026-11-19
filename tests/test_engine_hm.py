"""Heavy maintenance — section 6.1 :

coût HM/km = (coût HM 8 ans + coût HM 16 ans) / (16 × km de référence annuel)
coût mensuel = coût HM/km × km annuel ÷ 12 × coefficient HM
prix catalogue = max(coût × (1 + marge HM), BP HM) ; plancher = BP HM
"""

import pytest

from pricing_engine.engine import calculer_offre
from pricing_engine.models import Brique, Serie


def test_cout_hm_par_km(version_publiee):
    serie: Serie = version_publiee.series["VECTRON"]
    attendu = (150_000 + 200_000) / (16 * 120_000)
    assert serie.cout_hm_par_km == pytest.approx(attendu)


def test_prix_catalogue_hm_au_dessus_du_bp(version_publiee, config_base):
    offre = calculer_offre(version_publiee, config_base)
    hm = offre.par_brique[Brique.HEAVY_MAINTENANCE]

    cout_mensuel = (150_000 + 200_000) / (16 * 120_000) * 120_000 / 12 * 1.0
    assert cout_mensuel == pytest.approx(1822.9166666667)

    attendu_catalogue = cout_mensuel * 1.15
    assert hm.cout == pytest.approx(cout_mensuel)
    assert hm.prix_catalogue == pytest.approx(attendu_catalogue)
    assert hm.plancher == pytest.approx(2_000.0)  # BP HM
    assert hm.prix_retenu == pytest.approx(attendu_catalogue)


def test_plancher_hm_bloque_le_prix_catalogue_quand_le_bp_est_plus_haut(version_publiee, config_base):
    # À 80 000 km/an (bas de la tranche A), le BP HM (2 000) dépasse le coût + marge.
    config = config_base.model_copy(update={"km_annuel": 80_000})
    offre = calculer_offre(version_publiee, config)
    hm = offre.par_brique[Brique.HEAVY_MAINTENANCE]

    cout_mensuel = (150_000 + 200_000) / (16 * 120_000) * 80_000 / 12 * 1.0
    assert cout_mensuel * 1.15 < 2_000.0
    assert hm.prix_catalogue == pytest.approx(2_000.0)
    assert hm.plancher == pytest.approx(2_000.0)
