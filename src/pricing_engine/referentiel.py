"""Référentiel pricing versionné (M1).

- Une seule source de données, un propriétaire par table (M1-02).
- Versionné : brouillon / publié / archivé ; toute offre mémorise la version
  utilisée (M1-03).
- Contrôles qualité avant publication ; publication bloquée si anomalie
  bloquante (M1-04).
- Journal des modifications : qui, quand, avant, après, raison, validé par
  (M1-05).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel

from .models import (
    BudgetPlanEntry,
    Client,
    Locomotive,
    Parametres,
    Serie,
    TrancheKm,
    Validateur,
)

# Équipe propriétaire de chaque table (M1-02), cf. section 8.3.
PROPRIETAIRES: dict[str, str] = {
    "series": "Technique",
    "tranches_km": "Pricing",
    "grille_dry_lease": "Pricing",
    "budget_plan": "Finance",
    "clients": "Credit_Risque",
    "flotte": "Technique",
    "parametres": "Pricing",
    "delegations": "Direction",
}


class StatutVersion(str, Enum):
    BROUILLON = "brouillon"
    PUBLIE = "publie"
    ARCHIVE = "archive"


class AnomalieControleQualite(BaseModel):
    code: str
    message: str
    bloquante: bool


class EntreeJournal(BaseModel):
    version_numero: int
    horodatage: datetime
    utilisateur: str
    table: str
    action: str
    avant: Any
    apres: Any
    raison: str
    valide_par: str | None = None


@dataclass
class VersionReferentiel:
    numero: int
    statut: StatutVersion = StatutVersion.BROUILLON
    date_creation: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    date_publication: datetime | None = None
    publie_par: str | None = None

    series: dict[str, Serie] = field(default_factory=dict)
    tranches_km: list[TrancheKm] = field(default_factory=list)
    grille_dry_lease: list = field(default_factory=list)
    budget_plan: list[BudgetPlanEntry] = field(default_factory=list)
    clients: dict[str, Client] = field(default_factory=dict)
    flotte: dict[str, Locomotive] = field(default_factory=dict)
    parametres: Parametres = field(default_factory=Parametres)
    delegations: list[Validateur] = field(default_factory=list)

    def copier_brouillon(self, nouveau_numero: int) -> "VersionReferentiel":
        return VersionReferentiel(
            numero=nouveau_numero,
            statut=StatutVersion.BROUILLON,
            series=dict(self.series),
            tranches_km=list(self.tranches_km),
            grille_dry_lease=list(self.grille_dry_lease),
            budget_plan=list(self.budget_plan),
            clients=dict(self.clients),
            flotte=dict(self.flotte),
            parametres=self.parametres.model_copy(),
            delegations=list(self.delegations),
        )

    def tranche_km_pour(self, km_annuel: float) -> TrancheKm:
        for tranche in self.tranches_km:
            if tranche.contient(km_annuel):
                return tranche
        raise ValueError(f"Aucune tranche de km ne couvre {km_annuel} km/an")

    def bp_pour(self, serie_code: str, km_annuel: float) -> BudgetPlanEntry:
        for entree in self.budget_plan:
            if entree.serie_code == serie_code and entree.tranche_km.contient(km_annuel):
                return entree
        raise ValueError(f"Aucun BP pour la série {serie_code} à {km_annuel} km/an")

    def grille_pour(self, serie_code: str, duree_mois: int):
        for entree in self.grille_dry_lease:
            if entree.serie_code == serie_code and entree.tranche_duree.contient(duree_mois):
                return entree
        raise ValueError(f"Aucune grille Dry lease pour {serie_code} à {duree_mois} mois")

    def validateur_pour(self, niveau: int) -> Validateur | None:
        for validateur in self.delegations:
            if validateur.niveau == niveau:
                return validateur
        return None


class ReferentielBackend(Protocol):
    """Port de persistance du référentiel : une implémentation en mémoire
    (par défaut, pour les tests et le développement rapide) et une
    implémentation PostgreSQL (`db.SqlAlchemyReferentielBackend`, pour la
    version sur mesure sans Dataverse)."""

    def load_published(self) -> VersionReferentiel | None: ...
    def load(self, numero: int) -> VersionReferentiel: ...
    def save(self, version: VersionReferentiel) -> None: ...
    def next_numero(self) -> int: ...
    def append_journal(self, entry: EntreeJournal) -> None: ...
    def list_journal(self) -> list[EntreeJournal]: ...


class InMemoryReferentielBackend:
    """Backend par défaut : objets Python en mémoire, rien de persistant.

    Utilisé par les tests et par toute session `Referentiel()` sans backend
    explicite ; remplacé par `db.SqlAlchemyReferentielBackend` dès que
    `DATABASE_URL` est défini (voir `api.py`).
    """

    def __init__(self) -> None:
        self._versions: dict[int, VersionReferentiel] = {}
        self._prochain_numero = 1
        self._journal: list[EntreeJournal] = []

    def load_published(self) -> VersionReferentiel | None:
        candidates = [v for v in self._versions.values() if v.statut == StatutVersion.PUBLIE]
        return max(candidates, key=lambda v: v.numero, default=None)

    def load(self, numero: int) -> VersionReferentiel:
        return self._versions[numero]

    def save(self, version: VersionReferentiel) -> None:
        self._versions[version.numero] = version

    def next_numero(self) -> int:
        numero = self._prochain_numero
        self._prochain_numero += 1
        return numero

    def append_journal(self, entry: EntreeJournal) -> None:
        self._journal.append(entry)

    def list_journal(self) -> list[EntreeJournal]:
        return list(self._journal)


class Referentiel:
    """Dépôt versionné du référentiel pricing.

    Orchestration pure (versioning, contrôles qualité, journal) ; le
    stockage est délégué à un `ReferentielBackend` pluggable.
    """

    def __init__(self, backend: ReferentielBackend | None = None) -> None:
        self._backend = backend or InMemoryReferentielBackend()

    @property
    def journal(self) -> list[EntreeJournal]:
        return self._backend.list_journal()

    def version_publiee(self) -> VersionReferentiel | None:
        return self._backend.load_published()

    def version(self, numero: int) -> VersionReferentiel:
        return self._backend.load(numero)

    def nouveau_brouillon(self) -> VersionReferentiel:
        base = self._backend.load_published()
        numero = self._backend.next_numero()
        draft = base.copier_brouillon(numero) if base else VersionReferentiel(numero=numero)
        self._backend.save(draft)
        return draft

    def enregistrer_modification(
        self,
        draft: VersionReferentiel,
        table: str,
        action: str,
        avant: Any,
        apres: Any,
        utilisateur: str,
        raison: str,
        valide_par: str | None = None,
    ) -> None:
        """Persiste `draft` (tel qu'il a été mutable par l'appelant) et
        journalise le changement (M1-05)."""

        if table != "*" and table not in PROPRIETAIRES:
            raise ValueError(f"Table inconnue : {table}")
        self._backend.save(draft)
        self._backend.append_journal(
            EntreeJournal(
                version_numero=draft.numero,
                horodatage=datetime.now(timezone.utc),
                utilisateur=utilisateur,
                table=table,
                action=action,
                avant=avant,
                apres=apres,
                raison=raison,
                valide_par=valide_par,
            )
        )

    def controler_qualite(self, draft: VersionReferentiel) -> list[AnomalieControleQualite]:
        """Contrôles qualité avant publication (M1-04)."""

        anomalies: list[AnomalieControleQualite] = []

        series_codes = set(draft.series.keys())

        for loco in draft.flotte.values():
            if loco.serie_code not in series_codes:
                anomalies.append(
                    AnomalieControleQualite(
                        code="LOCO_SERIE_INCONNUE",
                        message=(
                            f"Locomotive {loco.numero} référence la série inconnue "
                            f"{loco.serie_code}"
                        ),
                        bloquante=True,
                    )
                )

        for entree in draft.grille_dry_lease:
            if entree.serie_code not in series_codes:
                anomalies.append(
                    AnomalieControleQualite(
                        code="GRILLE_SERIE_INCONNUE",
                        message=f"Grille Dry lease référence la série inconnue {entree.serie_code}",
                        bloquante=True,
                    )
                )

        for entree in draft.budget_plan:
            if entree.serie_code not in series_codes:
                anomalies.append(
                    AnomalieControleQualite(
                        code="BP_SERIE_INCONNUE",
                        message=f"BP référence la série inconnue {entree.serie_code}",
                        bloquante=True,
                    )
                )

        for serie_code in series_codes:
            a_une_grille = any(e.serie_code == serie_code for e in draft.grille_dry_lease)
            if not a_une_grille:
                anomalies.append(
                    AnomalieControleQualite(
                        code="GRILLE_MANQUANTE",
                        message=f"Aucune grille Dry lease pour la série {serie_code}",
                        bloquante=False,
                    )
                )
            a_un_bp = any(e.serie_code == serie_code for e in draft.budget_plan)
            if not a_un_bp:
                anomalies.append(
                    AnomalieControleQualite(
                        code="BP_MANQUANT",
                        message=f"Aucun BP HM/OM pour la série {serie_code}",
                        bloquante=False,
                    )
                )

        vus: set[tuple] = set()
        for entree in draft.grille_dry_lease:
            cle = (
                entree.serie_code,
                entree.tranche_duree.duree_min_mois,
                entree.tranche_duree.duree_max_mois,
            )
            if cle in vus:
                anomalies.append(
                    AnomalieControleQualite(
                        code="GRILLE_DOUBLON",
                        message=f"Doublon de grille Dry lease pour {cle}",
                        bloquante=True,
                    )
                )
            vus.add(cle)

        locos_vues: set[str] = set()
        for numero, loco in draft.flotte.items():
            if numero != loco.numero:
                anomalies.append(
                    AnomalieControleQualite(
                        code="LOCO_CLE_INCOHERENTE",
                        message=f"Clé {numero} ne correspond pas au numéro de la locomotive",
                        bloquante=True,
                    )
                )
            if loco.numero in locos_vues:
                anomalies.append(
                    AnomalieControleQualite(
                        code="LOCO_DOUBLON",
                        message=f"Doublon de locomotive {loco.numero}",
                        bloquante=True,
                    )
                )
            locos_vues.add(loco.numero)

        tranches_triees = sorted(draft.tranches_km, key=lambda t: t.km_min)
        borne_precedente: float | None = None
        for tranche in tranches_triees:
            if tranche.km_max is not None and tranche.km_max < tranche.km_min:
                anomalies.append(
                    AnomalieControleQualite(
                        code="TRANCHE_KM_BORNES_NON_CROISSANTES",
                        message=f"Tranche de km mal bornée : [{tranche.km_min}, {tranche.km_max}]",
                        bloquante=True,
                    )
                )
            if borne_precedente is not None and tranche.km_min < borne_precedente:
                anomalies.append(
                    AnomalieControleQualite(
                        code="TRANCHE_KM_CHEVAUCHEMENT",
                        message="Chevauchement entre tranches de km",
                        bloquante=True,
                    )
                )
            borne_precedente = tranche.km_max if tranche.km_max is not None else float("inf")

        for validateur in draft.delegations:
            if "@" not in validateur.email:
                anomalies.append(
                    AnomalieControleQualite(
                        code="VALIDATEUR_SANS_EMAIL",
                        message=f"Validateur niveau {validateur.niveau} sans e-mail valide",
                        bloquante=True,
                    )
                )

        for niveau in (1, 2, 3):
            if draft.validateur_pour(niveau) is None:
                anomalies.append(
                    AnomalieControleQualite(
                        code="VALIDATEUR_MANQUANT",
                        message=f"Aucun validateur configuré pour le niveau {niveau}",
                        bloquante=False,
                    )
                )

        return anomalies

    def publier(self, version_numero: int, utilisateur: str) -> list[AnomalieControleQualite]:
        """Publie un brouillon. Bloqué si une anomalie bloquante subsiste (M1-04)."""

        draft = self._backend.load(version_numero)
        if draft.statut != StatutVersion.BROUILLON:
            raise ValueError("Seul un brouillon peut être publié")

        anomalies = self.controler_qualite(draft)
        if any(a.bloquante for a in anomalies):
            return anomalies

        ancienne = self._backend.load_published()
        if ancienne is not None:
            ancienne.statut = StatutVersion.ARCHIVE
            self._backend.save(ancienne)

        draft.statut = StatutVersion.PUBLIE
        draft.date_publication = datetime.now(timezone.utc)
        draft.publie_par = utilisateur

        self.enregistrer_modification(
            draft,
            table="*",
            action="publication",
            avant=ancienne.numero if ancienne else None,
            apres=draft.numero,
            utilisateur=utilisateur,
            raison="Publication de version",
            valide_par=utilisateur,
        )
        return anomalies
