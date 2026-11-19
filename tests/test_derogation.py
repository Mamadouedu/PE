"""Circuit de dérogation — section 7, M4 : logique pure (backend mémoire)."""

import pytest

from pricing_engine.derogation import (
    DecisionInvalide,
    DerogationNonNecessaire,
    InMemoryDerogationStore,
    StatutDerogation,
    decider_derogation,
    demander_derogation,
)
from pricing_engine.models import Brique


def test_refuse_une_derogation_pour_une_offre_dans_les_regles(version_publiee, config_base):
    store = InMemoryDerogationStore()
    with pytest.raises(DerogationNonNecessaire):
        demander_derogation(store, version_publiee, config_base, "justification", "kam@akiem.com")


def test_cree_une_demande_avec_le_niveau_et_le_validateur_calcules(version_publiee, config_base):
    store = InMemoryDerogationStore()
    config = config_base.model_copy(update={"prix_negocies": {Brique.OPERATION_MAINTENANCE: 1_400.0}})

    derogation = demander_derogation(store, version_publiee, config, "remise fidélité", "kam@akiem.com")

    assert derogation.statut == StatutDerogation.EN_ATTENTE
    assert derogation.niveau == 2
    assert derogation.validateur_email == "head@akiem.com"
    assert derogation.demandeur == "kam@akiem.com"
    assert derogation.justification == "remise fidélité"
    assert derogation.client_code == "CLIENTOK"
    assert derogation.serie_code == "VECTRON"
    assert derogation.version_referentiel == version_publiee.numero
    assert derogation.date_decision is None


def test_demande_est_persistee_dans_le_registre(version_publiee, config_base):
    store = InMemoryDerogationStore()
    config = config_base.model_copy(update={"prix_negocies": {Brique.DRY_LEASE: 18_500.0}})

    derogation = demander_derogation(store, version_publiee, config, "négociation", "kam@akiem.com")

    assert store.obtenir(derogation.id).id == derogation.id
    assert [d.id for d in store.lister()] == [derogation.id]


def test_approbation_change_le_statut_et_trace_le_decideur(version_publiee, config_base):
    store = InMemoryDerogationStore()
    config = config_base.model_copy(update={"prix_negocies": {Brique.DRY_LEASE: 18_500.0}})
    derogation = demander_derogation(store, version_publiee, config, "négociation", "kam@akiem.com")

    decidee = decider_derogation(
        store, derogation.id, StatutDerogation.APPROUVEE, "manager@akiem.com", "ok pour ce coup-ci"
    )

    assert decidee.statut == StatutDerogation.APPROUVEE
    assert decidee.decideur == "manager@akiem.com"
    assert decidee.commentaire_decision == "ok pour ce coup-ci"
    assert decidee.date_decision is not None
    assert store.obtenir(derogation.id).statut == StatutDerogation.APPROUVEE


def test_rejet_change_le_statut(version_publiee, config_base):
    store = InMemoryDerogationStore()
    config = config_base.model_copy(update={"prix_negocies": {Brique.DRY_LEASE: 18_500.0}})
    derogation = demander_derogation(store, version_publiee, config, "négociation", "kam@akiem.com")

    decidee = decider_derogation(store, derogation.id, StatutDerogation.REJETEE, "manager@akiem.com", None)

    assert decidee.statut == StatutDerogation.REJETEE


def test_une_derogation_deja_decidee_ne_peut_pas_etre_redecidee(version_publiee, config_base):
    store = InMemoryDerogationStore()
    config = config_base.model_copy(update={"prix_negocies": {Brique.DRY_LEASE: 18_500.0}})
    derogation = demander_derogation(store, version_publiee, config, "négociation", "kam@akiem.com")
    decider_derogation(store, derogation.id, StatutDerogation.APPROUVEE, "manager@akiem.com", None)

    with pytest.raises(DecisionInvalide):
        decider_derogation(store, derogation.id, StatutDerogation.REJETEE, "manager@akiem.com", None)


def test_le_niveau_le_plus_eleve_determine_le_validateur(version_publiee, config_base):
    store = InMemoryDerogationStore()
    # Niveau 3 : prix très négociés, sous le coût de référence.
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

    derogation = demander_derogation(store, version_publiee, config, "cas extrême", "kam@akiem.com")

    assert derogation.niveau == 3
    assert derogation.validateur_email == "direction@akiem.com"
