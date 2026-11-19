"""Persistance PostgreSQL du référentiel (remplace Dataverse pour la version
sur mesure du cahier des charges, sans Power Apps).

Chaque version du référentiel est stockée comme un instantané JSON dans
`referentiel_versions` : une ligne par numéro de version, jamais réécrite
après publication (M1-03, brouillon / publié / archivé). Le journal des
modifications vit dans sa propre table relationnelle, interrogeable
indépendamment des versions (M1-05).

Ce choix — un instantané JSON plutôt que huit tables normalisées pour les
séries, grilles, tranches, BP, clients, flotte, paramètres, délégations —
est délibéré : le référentiel n'est jamais interrogé en SQL brut, seulement
à travers `pricing_engine.engine` et `pricing_engine.models` (Pydantic, déjà
la source de vérité du schéma). Normaliser dupliquerait cette validation
sans ajouter de capacité réelle à ce stade. À revoir si un outil externe
(Qlik Sense, par exemple) doit un jour lire le référentiel directement.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .models import (
    BudgetPlanEntry,
    Client,
    GrilleDryLeaseEntry,
    Locomotive,
    Parametres,
    Serie,
    TrancheKm,
    Validateur,
)
from .referentiel import EntreeJournal, StatutVersion, VersionReferentiel


class Base(DeclarativeBase):
    pass


class VersionRow(Base):
    __tablename__ = "referentiel_versions"

    numero: Mapped[int] = mapped_column(Integer, primary_key=True)
    statut: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    date_creation: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_publication: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publie_par: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class JournalRow(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_numero: Mapped[int] = mapped_column(
        ForeignKey("referentiel_versions.numero"), nullable=False, index=True
    )
    horodatage: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    utilisateur: Mapped[str] = mapped_column(String(255), nullable=False)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    avant: Mapped[Any] = mapped_column(JSON, nullable=True)
    apres: Mapped[Any] = mapped_column(JSON, nullable=True)
    raison: Mapped[str] = mapped_column(Text, nullable=False)
    valide_par: Mapped[str | None] = mapped_column(String(255))


def create_all(engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(database_url: str) -> sessionmaker[Session]:
    """Crée le moteur, s'assure que les tables existent, renvoie une
    fabrique de sessions. Pas d'Alembic à ce stade (voir README) : à mettre
    en place avant la mise en production."""

    engine = create_engine(database_url, pool_pre_ping=True)
    create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def _jsonable(value: Any) -> Any:
    """Sérialise une valeur de journal (avant/après) qui peut être un
    modèle Pydantic, une liste de modèles, un scalaire ou None."""

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, StatutVersion):
        return value.value
    return value


def _version_to_payload(version: VersionReferentiel) -> dict:
    return {
        "series": {code: s.model_dump(mode="json") for code, s in version.series.items()},
        "tranches_km": [t.model_dump(mode="json") for t in version.tranches_km],
        "grille_dry_lease": [g.model_dump(mode="json") for g in version.grille_dry_lease],
        "budget_plan": [b.model_dump(mode="json") for b in version.budget_plan],
        "clients": {code: c.model_dump(mode="json") for code, c in version.clients.items()},
        "flotte": {numero: loco.model_dump(mode="json") for numero, loco in version.flotte.items()},
        "parametres": version.parametres.model_dump(mode="json"),
        "delegations": [d.model_dump(mode="json") for d in version.delegations],
    }


def _payload_to_version(row: VersionRow) -> VersionReferentiel:
    payload = row.payload
    return VersionReferentiel(
        numero=row.numero,
        statut=StatutVersion(row.statut),
        date_creation=row.date_creation,
        date_publication=row.date_publication,
        publie_par=row.publie_par,
        series={code: Serie.model_validate(d) for code, d in payload["series"].items()},
        tranches_km=[TrancheKm.model_validate(d) for d in payload["tranches_km"]],
        grille_dry_lease=[
            GrilleDryLeaseEntry.model_validate(d) for d in payload["grille_dry_lease"]
        ],
        budget_plan=[BudgetPlanEntry.model_validate(d) for d in payload["budget_plan"]],
        clients={code: Client.model_validate(d) for code, d in payload["clients"].items()},
        flotte={numero: Locomotive.model_validate(d) for numero, d in payload["flotte"].items()},
        parametres=Parametres.model_validate(payload["parametres"]),
        delegations=[Validateur.model_validate(d) for d in payload["delegations"]],
    )


class SqlAlchemyReferentielBackend:
    """Backend PostgreSQL du référentiel (`ReferentielBackend`).

    Une session de courte durée par opération : simple et correct pour le
    volume attendu (quelques versions, quelques milliers d'écritures de
    journal) ; à revoir si le volume l'exige.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def load_published(self) -> VersionReferentiel | None:
        with self._session_factory() as session:
            row = session.execute(
                select(VersionRow)
                .where(VersionRow.statut == StatutVersion.PUBLIE.value)
                .order_by(VersionRow.numero.desc())
            ).scalars().first()
            return _payload_to_version(row) if row is not None else None

    def load(self, numero: int) -> VersionReferentiel:
        with self._session_factory() as session:
            row = session.get(VersionRow, numero)
            if row is None:
                raise KeyError(numero)
            return _payload_to_version(row)

    def save(self, version: VersionReferentiel) -> None:
        with self._session_factory() as session:
            row = session.get(VersionRow, version.numero)
            if row is None:
                row = VersionRow(numero=version.numero)
                session.add(row)
            row.statut = version.statut.value
            row.date_creation = version.date_creation
            row.date_publication = version.date_publication
            row.publie_par = version.publie_par
            row.payload = _version_to_payload(version)
            session.commit()

    def next_numero(self) -> int:
        with self._session_factory() as session:
            current_max = session.execute(select(func.max(VersionRow.numero))).scalar()
            return (current_max or 0) + 1

    def append_journal(self, entry: EntreeJournal) -> None:
        with self._session_factory() as session:
            session.add(
                JournalRow(
                    version_numero=entry.version_numero,
                    horodatage=entry.horodatage,
                    utilisateur=entry.utilisateur,
                    table_name=entry.table,
                    action=entry.action,
                    avant=_jsonable(entry.avant),
                    apres=_jsonable(entry.apres),
                    raison=entry.raison,
                    valide_par=entry.valide_par,
                )
            )
            session.commit()

    def list_journal(self) -> list[EntreeJournal]:
        with self._session_factory() as session:
            rows = session.execute(select(JournalRow).order_by(JournalRow.id)).scalars().all()
            return [
                EntreeJournal(
                    version_numero=r.version_numero,
                    horodatage=r.horodatage,
                    utilisateur=r.utilisateur,
                    table=r.table_name,
                    action=r.action,
                    avant=r.avant,
                    apres=r.apres,
                    raison=r.raison,
                    valide_par=r.valide_par,
                )
                for r in rows
            ]
