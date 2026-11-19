"""Tests d'intégration du backend PostgreSQL (db.py).

Contrairement aux autres tests (en mémoire, isolés), ceux-ci parlent à un
vrai PostgreSQL local et relisent systématiquement depuis une session /
un backend neuf — pour prouver une persistance réelle, pas seulement que
l'objet Python en mémoire garde son état.

Nécessite une base `pricing_test` accessible via TEST_DATABASE_URL (ou
l'URL par défaut ci-dessous) ; sinon, ces tests sont ignorés.
"""

from __future__ import annotations

import os
from datetime import date

import pytest
from sqlalchemy import create_engine, text

from pricing_engine.db import SqlAlchemyReferentielBackend, create_all, make_session_factory
from pricing_engine.models import Locomotive, Serie
from pricing_engine.referentiel import Referentiel, StatutVersion

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


def _serie_minimale(code: str = "S1") -> Serie:
    return Serie(
        code=code,
        valeur_neuve=1_000_000,
        km_reference_annuel=120_000,
        cout_hm_8_ans=100_000,
        cout_hm_16_ans=100_000,
        om_fixe=1_000,
        om_variable_eur_par_km=0.05,
        taux_assurance_annuel=0.03,
    )


@pytest.fixture(autouse=True)
def _base_propre():
    engine = create_engine(TEST_DATABASE_URL)
    create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE journal_entries, referentiel_versions, derogations "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield
    engine.dispose()


@pytest.fixture
def backend() -> SqlAlchemyReferentielBackend:
    return SqlAlchemyReferentielBackend(make_session_factory(TEST_DATABASE_URL))


def _nouveau_backend() -> SqlAlchemyReferentielBackend:
    """Un backend indépendant, pour vérifier une lecture qui ne passe pas
    par l'objet Python déjà utilisé pour écrire."""

    return SqlAlchemyReferentielBackend(make_session_factory(TEST_DATABASE_URL))


def test_brouillon_relu_depuis_un_backend_independant(backend):
    referentiel = Referentiel(backend)
    draft = referentiel.nouveau_brouillon()
    serie = _serie_minimale("VECTRON")
    draft.series["VECTRON"] = serie
    referentiel.enregistrer_modification(
        draft, "series", "set", None, serie, "kam@akiem.com", "Création série"
    )

    relu = _nouveau_backend().load(draft.numero)

    assert relu.statut == StatutVersion.BROUILLON
    assert relu.series["VECTRON"].valeur_neuve == 1_000_000


def test_publication_persiste_et_archive_la_version_precedente(backend):
    referentiel = Referentiel(backend)

    draft1 = referentiel.nouveau_brouillon()
    draft1.series["S1"] = _serie_minimale()
    referentiel.enregistrer_modification(
        draft1, "series", "set", None, draft1.series["S1"], "pricing@akiem.com", "init"
    )
    anomalies1 = referentiel.publier(draft1.numero, "pricing@akiem.com")
    assert not any(a.bloquante for a in anomalies1)

    draft2 = referentiel.nouveau_brouillon()
    assert draft2.series["S1"].code == "S1"  # copié depuis la version publiée, relue en base
    anomalies2 = referentiel.publier(draft2.numero, "pricing@akiem.com")
    assert not any(a.bloquante for a in anomalies2)

    autre = _nouveau_backend()
    assert autre.load(draft1.numero).statut == StatutVersion.ARCHIVE
    assert autre.load_published().numero == draft2.numero


def test_publication_bloquante_ne_change_rien_en_base(backend):
    referentiel = Referentiel(backend)
    draft = referentiel.nouveau_brouillon()
    loco = Locomotive(
        numero="L1", serie_code="INCONNUE", mise_en_service=date(2020, 1, 1), km_cumules=0
    )
    draft.flotte["L1"] = loco
    referentiel.enregistrer_modification(
        draft, "flotte", "set", None, loco, "pricing@akiem.com", "ajout loco"
    )

    anomalies = referentiel.publier(draft.numero, "pricing@akiem.com")
    assert any(a.bloquante for a in anomalies)

    autre = _nouveau_backend()
    assert autre.load(draft.numero).statut == StatutVersion.BROUILLON
    assert autre.load_published() is None


def test_journal_est_persiste_et_requetable_independamment(backend):
    referentiel = Referentiel(backend)
    draft = referentiel.nouveau_brouillon()
    serie = _serie_minimale()
    referentiel.enregistrer_modification(
        draft, "series", "set", None, serie, "kam@akiem.com", "Création série"
    )

    entrees = _nouveau_backend().list_journal()

    assert len(entrees) == 1
    assert entrees[0].version_numero == draft.numero
    assert entrees[0].table == "series"
    assert entrees[0].utilisateur == "kam@akiem.com"
    assert entrees[0].apres["code"] == "S1"


def test_build_referentiel_bascule_sur_postgres_si_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    from pricing_engine.api import _build_referentiel

    referentiel = _build_referentiel()
    draft = referentiel.nouveau_brouillon()

    # Vérification directe en base, indépendante de l'objet Python retourné.
    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as conn:
        statut = conn.execute(
            text("SELECT statut FROM referentiel_versions WHERE numero = :n"),
            {"n": draft.numero},
        ).scalar_one()
    assert statut == "brouillon"
