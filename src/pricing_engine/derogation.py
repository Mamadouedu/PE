"""Circuit de dérogation (M4, section 7 du cahier des charges).

Le niveau de validation est calculé par le moteur de prix, jamais choisi par
le KAM (M4-01). Ce module encapsule ce qui l'entoure : la demande (avec
justification obligatoire, M4-02), l'envoi au bon validateur par webhook
(M4-03 — Power Automate et Teams restent responsables du rappel et de
l'escalade après délai, hors périmètre de ce module), la décision, et le
registre central (M4-05).

Une dérogation gèle la configuration exacte qui l'a déclenchée
(`Derogation.configuration`) : une offre approuvée reste liée à cette
configuration précise, jamais à « la dernière version » de l'offre — c'est
ce qui rend une approbation caduque dès que le KAM modifie quoi que ce soit
(M4-04). Vérifier cette correspondance avant l'envoi effectif d'une offre
revient au futur M3-05/M3-06, pas à ce module.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

import httpx
from pydantic import BaseModel

from .engine import calculer_offre, validateur_requis
from .models import ConfigurationOffre
from .referentiel import VersionReferentiel


class StatutDerogation(str, Enum):
    EN_ATTENTE = "en_attente"
    APPROUVEE = "approuvee"
    REJETEE = "rejetee"


class Derogation(BaseModel):
    id: int
    statut: StatutDerogation
    niveau: int
    demandeur: str
    justification: str
    configuration: ConfigurationOffre
    version_referentiel: int
    client_code: str
    serie_code: str
    montant_mensuel_retenu: float
    validateur_email: str | None
    date_demande: datetime
    date_decision: datetime | None = None
    decideur: str | None = None
    commentaire_decision: str | None = None


class DerogationNonNecessaire(ValueError):
    """Levée quand l'offre est dans les règles (niveau 0) : rien à demander."""


class DecisionInvalide(ValueError):
    """Levée sur une décision déjà prise, ou une valeur de décision invalide."""


class DerogationStore(Protocol):
    def prochain_id(self) -> int: ...
    def creer(self, derogation: Derogation) -> Derogation: ...
    def obtenir(self, id_: int) -> Derogation: ...
    def lister(self) -> list[Derogation]: ...
    def mettre_a_jour(self, derogation: Derogation) -> None: ...


class InMemoryDerogationStore:
    """Backend par défaut : rien de persistant, pour les tests et le
    développement rapide. Remplacé par `db.SqlAlchemyDerogationStore` dès
    que `DATABASE_URL` est défini (voir `api.py`)."""

    def __init__(self) -> None:
        self._derogations: dict[int, Derogation] = {}
        self._prochain_id = 1

    def prochain_id(self) -> int:
        id_ = self._prochain_id
        self._prochain_id += 1
        return id_

    def creer(self, derogation: Derogation) -> Derogation:
        self._derogations[derogation.id] = derogation
        return derogation

    def obtenir(self, id_: int) -> Derogation:
        return self._derogations[id_]

    def lister(self) -> list[Derogation]:
        return sorted(self._derogations.values(), key=lambda d: d.id, reverse=True)

    def mettre_a_jour(self, derogation: Derogation) -> None:
        self._derogations[derogation.id] = derogation


def demander_derogation(
    store: DerogationStore,
    version: VersionReferentiel,
    configuration: ConfigurationOffre,
    justification: str,
    demandeur: str,
) -> Derogation:
    """Calcule le niveau requis et crée la demande. Lève
    `DerogationNonNecessaire` si l'offre est déjà dans les règles."""

    offre = calculer_offre(version, configuration)
    if offre.niveau_validation == 0:
        raise DerogationNonNecessaire()

    validateur = validateur_requis(version, offre)

    derogation = Derogation(
        id=store.prochain_id(),
        statut=StatutDerogation.EN_ATTENTE,
        niveau=offre.niveau_validation,
        demandeur=demandeur,
        justification=justification,
        configuration=configuration,
        version_referentiel=version.numero,
        client_code=configuration.client_code,
        serie_code=configuration.serie_code,
        montant_mensuel_retenu=offre.total_retenu_mensuel,
        validateur_email=validateur.email if validateur else None,
        date_demande=datetime.now(timezone.utc),
    )
    store.creer(derogation)
    _notifier_power_automate(derogation)
    return derogation


def decider_derogation(
    store: DerogationStore,
    id_: int,
    decision: StatutDerogation,
    decideur: str,
    commentaire: str | None,
) -> Derogation:
    """Enregistre la décision du validateur. Lève `DecisionInvalide` si la
    dérogation a déjà été décidée, ou si `decision` n'est pas une décision
    valide (seules APPROUVEE et REJETEE le sont)."""

    derogation = store.obtenir(id_)
    if derogation.statut != StatutDerogation.EN_ATTENTE:
        raise DecisionInvalide("Cette dérogation a déjà été décidée")
    if decision not in (StatutDerogation.APPROUVEE, StatutDerogation.REJETEE):
        raise DecisionInvalide("Décision invalide")

    derogation.statut = decision
    derogation.decideur = decideur
    derogation.commentaire_decision = commentaire
    derogation.date_decision = datetime.now(timezone.utc)
    store.mettre_a_jour(derogation)
    return derogation


def _notifier_power_automate(derogation: Derogation) -> None:
    """Best-effort : une dérogation se crée même si Power Automate est
    injoignable ou non configuré (dev, tests). M4-03 (rappel, escalade,
    suppléant) est la responsabilité du flow déclenché ici, pas de ce code."""

    url = os.environ.get("POWER_AUTOMATE_WEBHOOK_URL")
    if not url:
        return

    payload = {
        "derogation_id": derogation.id,
        "niveau": derogation.niveau,
        "validateur_email": derogation.validateur_email,
        "demandeur": derogation.demandeur,
        "client_code": derogation.client_code,
        "serie_code": derogation.serie_code,
        "montant_mensuel_retenu": derogation.montant_mensuel_retenu,
        "justification": derogation.justification,
    }
    try:
        httpx.post(url, json=payload, timeout=5.0)
    except Exception:  # noqa: BLE001 — webhook best-effort, ne bloque jamais la demande
        pass
