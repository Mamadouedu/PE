"""Niveaux de validation — section 6.3 : le niveau le plus élevé s'applique,
il est toujours calculé par la plateforme, jamais choisi par le KAM."""

import pytest

from pricing_engine.engine import calculer_offre, validateur_requis
from pricing_engine.models import Brique


def test_niveau_0_dans_les_regles(version_publiee, config_base):
    offre = calculer_offre(version_publiee, config_base)

    assert offre.niveau_validation == 0
    assert offre.tous_controles_ok
    assert offre.remise_globale <= version_publiee.parametres.seuil_remise_kam
    assert validateur_requis(version_publiee, offre) is None


def test_niveau_1_remise_superieure_au_seuil_kam(version_publiee, config_base):
    config = config_base.model_copy(update={"prix_negocies": {Brique.DRY_LEASE: 18_500.0}})
    offre = calculer_offre(version_publiee, config)

    assert offre.remise_globale > version_publiee.parametres.seuil_remise_kam
    assert offre.par_brique[Brique.DRY_LEASE].prix_retenu >= offre.par_brique[Brique.DRY_LEASE].plancher
    assert offre.niveau_validation == 1
    assert validateur_requis(version_publiee, offre).nom == "Manager"


def test_niveau_2_brique_sous_plancher(version_publiee, config_base):
    config = config_base.model_copy(update={"prix_negocies": {Brique.OPERATION_MAINTENANCE: 1_400.0}})
    offre = calculer_offre(version_publiee, config)

    assert offre.par_brique[Brique.OPERATION_MAINTENANCE].prix_retenu < offre.par_brique[Brique.OPERATION_MAINTENANCE].plancher
    assert offre.niveau_validation == 2
    assert validateur_requis(version_publiee, offre).nom == "Head of Pricing"


def test_niveau_2_controle_en_echec(version_publiee, config_base):
    # Client sans aucune garantie de paiement => contrôle C5 en échec.
    config = config_base.model_copy(update={"client_code": "CLIENTNG"})
    offre = calculer_offre(version_publiee, config)

    assert not offre.tous_controles_ok
    assert offre.niveau_validation == 2


def test_niveau_3_prix_sous_le_cout_de_reference(version_publiee, config_base):
    config = config_base.model_copy(
        update={
            "prix_negocies": {
                Brique.DRY_LEASE: 100.0,
                Brique.HEAVY_MAINTENANCE: 100.0,
                Brique.OPERATION_MAINTENANCE: 100.0,
                Brique.ASSURANCE: 100.0,
            }
        }
    )
    offre = calculer_offre(version_publiee, config)

    assert offre.total_retenu_par_loco_mensuel < offre.cout_reference_mensuel
    assert offre.niveau_validation == 3
    assert validateur_requis(version_publiee, offre).nom == "Direction"


def test_le_niveau_le_plus_eleve_s_applique(version_publiee, config_base):
    # Remise > seuil KAM (niveau 1) ET brique sous plancher (niveau 2) :
    # le niveau retenu doit être 2, pas 1.
    config = config_base.model_copy(
        update={
            "prix_negocies": {
                Brique.DRY_LEASE: 18_500.0,
                Brique.OPERATION_MAINTENANCE: 1_400.0,
            }
        }
    )
    offre = calculer_offre(version_publiee, config)
    assert offre.niveau_validation == 2
