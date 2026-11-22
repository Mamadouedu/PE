"""Assistant conversationnel pour le KAM (M3-08).

Deux implémentations :

- `AnthropicAssistant` : appelle l'API Anthropic Claude en direct (httpx)
  avec un prompt système qui connaît les règles métier du moteur de prix.
  Nécessite `ANTHROPIC_API_KEY`.
- `ScriptedAssistant` : repli déterministe sans LLM. Détecte quelques
  mots-clés (prix, dérogation, contrôles…) et renvoie une réponse canée.
  Suffisant pour démo, debug et déploiements sans sortie Internet.

Le choix se fait côté `api.py` : si la clé est présente on prend
`AnthropicAssistant`, sinon `ScriptedAssistant`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

Role = Literal["user", "assistant"]


@dataclass
class Message:
    role: Role
    content: str


@dataclass
class ReponseAssistant:
    message: str
    moteur: str  # "anthropic" | "scripted"


SYSTEM_PROMPT = """\
Tu es l'assistant du configurateur KAM de la plateforme Pricing Akiem.
Tu aides un Key Account Manager à :
- comprendre comment chiffrer une offre de location full service
  (Dry lease + HM + OM + Assurance) ;
- interpréter le niveau de validation (0 KAM, 1 Manager, 2 Head of Pricing,
  3 Direction) et les 8 contrôles avant envoi ;
- construire une demande de dérogation (justification obligatoire) ;
- comprendre le référentiel (séries, clients, flotte, grilles, BP).

Tu n'inventes pas de prix et tu ne négocies pas à la place du KAM.
Réponds en français, de manière concise (max 6 phrases).
Si la question sort de ton périmètre, dis-le poliment.
"""


class Assistant(Protocol):
    def repondre(self, historique: list[Message]) -> ReponseAssistant: ...


class AnthropicAssistant:
    """Appelle l'API Anthropic Claude via httpx. Pas de dépendance sur le
    SDK anthropic pour rester léger."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-5-5",
        *,
        max_tokens: int = 500,
        timeout: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._timeout = timeout

    def repondre(self, historique: list[Message]) -> ReponseAssistant:
        payload = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": m.role, "content": m.content} for m in historique],
        }
        try:
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            return ReponseAssistant(f"L'assistant est indisponible (erreur réseau : {exc}).", "anthropic")

        if r.status_code >= 400:
            return ReponseAssistant(
                f"L'assistant a répondu HTTP {r.status_code}. Recommence dans quelques instants.",
                "anthropic",
            )

        corps = r.json()
        morceaux = corps.get("content", [])
        texte = "".join(m.get("text", "") for m in morceaux if m.get("type") == "text")
        return ReponseAssistant(texte or "(Réponse vide de l'assistant.)", "anthropic")


class ScriptedAssistant:
    """Assistant de repli sans LLM : détecte quelques mots-clés et renvoie
    une réponse canée. Suffisant pour les démos et quand `ANTHROPIC_API_KEY`
    n'est pas défini."""

    REPONSES: list[tuple[list[str], str]] = [
        (
            ["bonjour", "salut", "hello", "coucou"],
            "Bonjour ! Je suis l'assistant du configurateur Akiem. Je peux t'expliquer le chiffrage, le niveau de validation, les contrôles avant envoi ou la demande de dérogation. Par quoi veux-tu commencer ?",
        ),
        (
            ["niveau", "validation"],
            "Le niveau de validation est recalculé par le moteur : 0 = KAM OK, 1 = Manager, 2 = Head of Pricing, 3 = Direction. Il grimpe quand tu négocies sous le plancher ou quand la remise globale dépasse le seuil paramétré. Le KAM ne peut jamais choisir le niveau lui-même (M4-01).",
        ),
        (
            ["contrôle", "controle", "C1", "C2", "C3", "C8"],
            "Les 8 contrôles vérifient : durée vs campagne (C1), nombre de locos (C2), client à rating élevé (C3), assurance incluse (C4), garantie de paiement (C5), aucun prix sous plancher BP (C6), DL couvre la perte de valeur (C7), locomotive disponible et bonne série (C8). Un contrôle au rouge n'empêche pas de chiffrer mais apparaît dans l'offre et doit être justifié.",
        ),
        (
            ["dérogation", "derogation"],
            "Une dérogation est nécessaire dès que le niveau de validation > 0. Tu dois fournir une justification (obligatoire). La demande file au bon validateur selon ton tableau de délégations, et sa décision revient par webhook Power Automate. Tu peux suivre son statut en direct dans le registre central.",
        ),
        (
            ["brique", "dry lease", "HM", "OM", "assurance"],
            "Une offre se décompose en 4 briques : Dry lease (loyer de la machine, grille × coefficient de tranche de km), HM (heavy maintenance, BP × coefficient), OM (operation maintenance, fixe + variable au km), et Assurance (% de la VR moyenne). Chaque brique a un coût, un plancher BP et un prix catalogue — le prix retenu peut être négocié entre les deux.",
        ),
        (
            ["pdf", "offre"],
            "L'offre PDF numérotée `AK-XXXXXX` est produite par POST /api/v1/offres/pdf. Elle ne montre jamais au client ni le catalogue ni le plancher : seulement le prix retenu. Elle porte la mention PROJET tant que la validation n'est pas acquise.",
        ),
        (
            ["référentiel", "referentiel", "version", "publier", "brouillon"],
            "Le référentiel est versionné : tu crées un brouillon, tu l'édites, tu lances les contrôles qualité, tu publies. Une offre chiffrée fige la version du référentiel qui a servi au calcul — pas de prix recalculé en douce si tu publies une nouvelle version.",
        ),
        (
            ["pipedrive", "crm", "deal"],
            "Dès que `PIPEDRIVE_API_TOKEN` et `PIPEDRIVE_COMPANY_DOMAIN` sont définis, chaque PDF généré pousse aussi un deal dans Pipedrive (M3-06). L'ID du deal apparaît dans le registre des offres. Un échec Pipedrive n'empêche jamais la production du PDF.",
        ),
    ]

    REPONSE_DEFAUT = (
        "Je ne suis pas sûr de bien saisir. Tu peux me demander : comment chiffrer une offre, "
        "comment le niveau de validation est calculé, quels sont les 8 contrôles avant envoi, "
        "comment demander une dérogation, ou comment publier une nouvelle version du référentiel."
    )

    def repondre(self, historique: list[Message]) -> ReponseAssistant:
        if not historique:
            return ReponseAssistant(
                "Bonjour ! Pose-moi une question sur la plateforme (chiffrage, contrôles, dérogation, référentiel, PDF…).",
                "scripted",
            )
        dernier = historique[-1]
        question = dernier.content.lower()
        for mots, reponse in self.REPONSES:
            if any(m.lower() in question for m in mots):
                return ReponseAssistant(reponse, "scripted")
        return ReponseAssistant(self.REPONSE_DEFAUT, "scripted")
