"""Persistance PostgreSQL de la numérotation des offres (M3-05 / M3-06).

Même principe que les autres tests Postgres : relire depuis un store
indépendant pour prouver une vraie persistance, et vérifier que la
séquence ne se remet jamais à zéro.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from pricing_engine.db import SqlAlchemyOffreGenereeStore, create_all, make_session_factory
from pricing_engine.offre_pdf import generer_offre

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
        conn.execute(text("TRUNCATE offres_generees RESTART IDENTITY CASCADE"))
    yield
    engine.dispose()


def _nouveau_store() -> SqlAlchemyOffreGenereeStore:
    return SqlAlchemyOffreGenereeStore(make_session_factory(TEST_DATABASE_URL))


def test_offre_relue_depuis_un_store_independant(version_publiee, config_base):
    store = _nouveau_store()

    offre, pdf_bytes = generer_offre(store, version_publiee, config_base, "kam@akiem.com")

    assert offre.numero == "AK-000001"
    assert pdf_bytes[:4] == b"%PDF"
    relue = _nouveau_store().lister()
    assert len(relue) == 1
    assert relue[0].numero == "AK-000001"
    assert relue[0].configuration.client_code == "CLIENTOK"


def test_la_sequence_ne_se_remet_jamais_a_zero(version_publiee, config_base):
    store = _nouveau_store()
    generer_offre(store, version_publiee, config_base, "kam@akiem.com")

    # Nouveau store, nouvelle session : la séquence doit repartir du dernier
    # numéro persisté, pas de zéro.
    deuxieme_offre, _ = generer_offre(_nouveau_store(), version_publiee, config_base, "kam@akiem.com")

    assert deuxieme_offre.numero == "AK-000002"
