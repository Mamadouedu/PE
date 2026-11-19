"""Dry lease — section 6.1 : prix catalogue = grille × coefficient DL ;
plancher = catalogue × (1 - remise max)."""

import pytest

from pricing_engine.engine import calculer_offre
from pricing_engine.models import Brique


def test_prix_catalogue_et_plancher_dry_lease(version_publiee, config_base):
    offre = calculer_offre(version_publiee, config_base)
    dl = offre.par_brique[Brique.DRY_LEASE]

    assert dl.prix_catalogue == pytest.approx(20_000.0)
    assert dl.plancher == pytest.approx(20_000.0 * 0.90)
    assert dl.prix_retenu == pytest.approx(20_000.0)


def test_coefficient_dl_change_selon_la_tranche_de_km(version_publiee, config_base):
    config_tranche_b = config_base.model_copy(update={"km_annuel": 160_000})
    offre = calculer_offre(version_publiee, config_tranche_b)
    dl = offre.par_brique[Brique.DRY_LEASE]

    # tranche B : coefficient_dl = 1.05
    assert dl.prix_catalogue == pytest.approx(20_000.0 * 1.05)


def test_prix_negocie_sous_plancher_est_signale(version_publiee, config_base):
    config = config_base.model_copy(update={"prix_negocies": {Brique.DRY_LEASE: 17_000.0}})
    offre = calculer_offre(version_publiee, config)
    dl = offre.par_brique[Brique.DRY_LEASE]

    assert dl.prix_retenu == pytest.approx(17_000.0)
    assert dl.prix_retenu < dl.plancher


def test_brique_exclue_vaut_zero(version_publiee, config_base):
    config = config_base.model_copy(
        update={
            "briques_incluses": {
                Brique.HEAVY_MAINTENANCE,
                Brique.OPERATION_MAINTENANCE,
                Brique.ASSURANCE,
            }
        }
    )
    offre = calculer_offre(version_publiee, config)
    dl = offre.par_brique[Brique.DRY_LEASE]

    assert dl.prix_retenu == 0.0
