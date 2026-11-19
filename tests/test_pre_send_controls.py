"""Les 8 contrôles avant envoi — section 6.4."""

import pytest

from pricing_engine.engine import calculer_offre
from pricing_engine.models import Brique


def _controle(offre, code):
    return next(c for c in offre.controles if c.code == code)


def test_c1_duree_campagne_en_echec(version_publiee, config_base):
    config = config_base.model_copy(update={"campagne": True, "duree_mois": 4})
    offre = calculer_offre(version_publiee, config)
    assert _controle(offre, "C1_DUREE_CAMPAGNE").ok is False


def test_c1_non_applicable_hors_campagne(version_publiee, config_base):
    config = config_base.model_copy(update={"campagne": False, "duree_mois": 4})
    offre = calculer_offre(version_publiee, config)
    assert _controle(offre, "C1_DUREE_CAMPAGNE").ok is True


def test_c2_nombre_de_locos_en_echec(version_publiee, config_base):
    config = config_base.model_copy(update={"quantite": 3})
    offre = calculer_offre(version_publiee, config)
    assert _controle(offre, "C2_NB_LOCOS").ok is False


def test_c3_rating_eleve_sans_paiement_rapide_en_echec(version_publiee, config_base):
    config = config_base.model_copy(update={"client_code": "CLIENTHR", "duree_mois": 2})
    offre = calculer_offre(version_publiee, config)
    assert _controle(offre, "C3_CLIENT_RATING").ok is False


def test_c3_rating_eleve_avec_duree_courte_et_avance_ok(version_publiee, config_base):
    config = config_base.model_copy(update={"client_code": "CLIENTHR", "duree_mois": 1})
    offre = calculer_offre(version_publiee, config)
    assert _controle(offre, "C3_CLIENT_RATING").ok is True


def test_c4_assurance_exclue_en_echec(version_publiee, config_base):
    config = config_base.model_copy(
        update={
            "briques_incluses": {
                Brique.DRY_LEASE,
                Brique.HEAVY_MAINTENANCE,
                Brique.OPERATION_MAINTENANCE,
            }
        }
    )
    offre = calculer_offre(version_publiee, config)
    assert _controle(offre, "C4_ASSURANCE_INCLUSE").ok is False


def test_c5_sans_garantie_de_paiement_en_echec(version_publiee, config_base):
    config = config_base.model_copy(update={"client_code": "CLIENTNG"})
    offre = calculer_offre(version_publiee, config)
    assert _controle(offre, "C5_GARANTIE_PAIEMENT").ok is False


def test_c6_prix_sous_le_plancher_bp_en_echec(version_publiee, config_base):
    config = config_base.model_copy(update={"prix_negocies": {Brique.OPERATION_MAINTENANCE: 1_400.0}})
    offre = calculer_offre(version_publiee, config)
    assert _controle(offre, "C6_AUCUN_PRIX_SOUS_PLANCHER_BP").ok is False


def test_c7_dry_lease_ne_couvre_pas_la_perte_de_valeur_en_echec(version_publiee, config_base):
    config = config_base.model_copy(update={"prix_negocies": {Brique.DRY_LEASE: 3_000.0}})
    offre = calculer_offre(version_publiee, config)
    assert _controle(offre, "C7_DL_COUVRE_PERTE_VALEUR").ok is False


def test_c8_locomotive_en_maintenance_en_echec(version_publiee, config_base):
    config = config_base.model_copy(
        update={"locomotive_numero": "LOCOKO", "age_debut_ans": None, "km_cumules_debut": None}
    )
    offre = calculer_offre(version_publiee, config)
    assert _controle(offre, "C8_LOCO_DISPONIBLE_BONNE_SERIE").ok is False


def test_c8_locomotive_mauvaise_serie_en_echec(version_publiee, config_base):
    config = config_base.model_copy(
        update={"locomotive_numero": "LOCOAS", "age_debut_ans": None, "km_cumules_debut": None}
    )
    offre = calculer_offre(version_publiee, config)
    assert _controle(offre, "C8_LOCO_DISPONIBLE_BONNE_SERIE").ok is False


def test_c8_locomotive_disponible_bonne_serie_ok(version_publiee, config_base):
    config = config_base.model_copy(
        update={"locomotive_numero": "LOCOOK", "age_debut_ans": None, "km_cumules_debut": None}
    )
    offre = calculer_offre(version_publiee, config)
    assert _controle(offre, "C8_LOCO_DISPONIBLE_BONNE_SERIE").ok is True


def test_tous_les_controles_passent_sur_la_configuration_de_base(version_publiee, config_base):
    offre = calculer_offre(version_publiee, config_base)
    assert all(c.ok for c in offre.controles)
    assert offre.tous_controles_ok
