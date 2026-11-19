"""Persistance PostgreSQL du registre des dérogations (M4-05).

Même principe que `test_db_postgres.py` : relire depuis un store
indépendant pour prouver une vraie persistance.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from pricing_engine.db import SqlAlchemyDerogationStore, create_all, make_session_factory
from pricing_engine.derogation import StatutDerogation, decider_derogation, demander_derogation
from pricing_engine.models import Brique

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://pricing:pricing@localhost/pricing_test"
)


def _postgres_disponible() -> bool:
    try:
        with create_engine(TEST_DATABASE_URL).connect():
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_disponible(),
    reason=f"PostgreSQL de test indisponible ({TEST_DATABASE_URL})",
)


@pytest.fixture(autouse=True)
def _base_propre():
    engine = create_engine(TEST_DATABASE_URL)
    create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE derogations RESTART IDENTITY CASCADE"))
    yield
    engine.dispose()


def _nouveau_store() -> SqlAlchemyDerogationStore:
    return SqlAlchemyDerogationStore(make_session_factory(TEST_DATABASE_URL))


def test_demande_relue_depuis_un_store_independant(version_publiee, config_base):
    store = _nouveau_store()
    config = config_base.model_copy(update={"prix_negocies": {Brique.OPERATION_MAINTENANCE: 1_400.0}})

    derogation = demander_derogation(store, version_publiee, config, "remise fidélité", "kam@akiem.com")

    relue = _nouveau_store().obtenir(derogation.id)
    assert relue.statut == StatutDerogation.EN_ATTENTE
    assert relue.niveau == 2
    assert relue.validateur_email == "head@akiem.com"
    assert relue.configuration.client_code == "CLIENTOK"
    # La configuration complète a bien traversé le JSON : la négociation
    # qui a déclenché la dérogation est toujours là.
    assert relue.configuration.prix_negocies[Brique.OPERATION_MAINTENANCE] == 1_400.0


def test_decision_persiste_et_se_relit(version_publiee, config_base):
    store = _nouveau_store()
    config = config_base.model_copy(update={"prix_negocies": {Brique.DRY_LEASE: 18_500.0}})
    derogation = demander_derogation(store, version_publiee, config, "négociation", "kam@akiem.com")

    decider_derogation(
        store, derogation.id, StatutDerogation.APPROUVEE, "manager@akiem.com", "validé en direct"
    )

    relue = _nouveau_store().obtenir(derogation.id)
    assert relue.statut == StatutDerogation.APPROUVEE
    assert relue.decideur == "manager@akiem.com"
    assert relue.commentaire_decision == "validé en direct"
    assert relue.date_decision is not None


def test_le_registre_liste_toutes_les_demandes(version_publiee, config_base):
    store = _nouveau_store()
    c1 = config_base.model_copy(update={"prix_negocies": {Brique.DRY_LEASE: 18_500.0}})
    c2 = config_base.model_copy(update={"prix_negocies": {Brique.OPERATION_MAINTENANCE: 1_400.0}})
    demander_derogation(store, version_publiee, c1, "a", "kam1@akiem.com")
    demander_derogation(store, version_publiee, c2, "b", "kam2@akiem.com")

    registre = _nouveau_store().lister()

    assert len(registre) == 2
    assert {d.demandeur for d in registre} == {"kam1@akiem.com", "kam2@akiem.com"}
