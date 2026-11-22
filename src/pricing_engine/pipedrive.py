"""Pont Pipedrive (M3-06, part « écriture du deal »).

Au moment où une offre PDF est générée, on souhaite aussi créer un deal
dans Pipedrive pour que le CRM commercial ait la trace sans que le KAM
ait à ressaisir. Deux implémentations :

- `HttpPipedriveBridge` : appelle l'API v1 Pipedrive (`POST /v1/deals`).
  Nécessite `PIPEDRIVE_API_TOKEN` et `PIPEDRIVE_COMPANY_DOMAIN`.
- `NoOpPipedriveBridge` : ne fait rien. C'est le bridge actif tant que
  Pipedrive n'est pas configuré. Permet à l'API de fonctionner telle quelle
  en local.

L'appel est best-effort : si Pipedrive refuse ou est injoignable, on
enregistre l'offre quand même sans `pipedrive_deal_*`. Une erreur réseau
n'empêche jamais la génération du PDF.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from .offre_pdf import OffreGeneree


@dataclass
class PipedriveResultat:
    deal_id: int | None
    deal_url: str | None
    statut: str  # "pousse" | "echec" | "non_configure"
    erreur: str | None = None


class PipedriveBridge(Protocol):
    def pousser_deal(self, offre: OffreGeneree) -> PipedriveResultat: ...


class NoOpPipedriveBridge:
    """Backend par défaut : ne fait rien. Retourne toujours un résultat
    `non_configure` pour qu'on sache visuellement que l'intégration n'est
    pas active."""

    def pousser_deal(self, offre: OffreGeneree) -> PipedriveResultat:
        return PipedriveResultat(deal_id=None, deal_url=None, statut="non_configure")


class HttpPipedriveBridge:
    """Pousse un deal via l'API v1 Pipedrive (`POST /v1/deals`).

    `company_domain` est le sous-domaine Pipedrive de l'organisation
    (ex. "akiem" pour https://akiem.pipedrive.com).
    """

    def __init__(self, api_token: str, company_domain: str, *, timeout: float = 10.0) -> None:
        self._api_token = api_token
        self._base_url = f"https://{company_domain}.pipedrive.com/v1"
        self._timeout = timeout

    def pousser_deal(self, offre: OffreGeneree) -> PipedriveResultat:
        valeur = offre.montant_mensuel_retenu * offre.configuration.duree_mois
        titre = (
            f"{offre.numero} — {offre.client_code} / {offre.serie_code}"
            f" × {offre.configuration.quantite}"
            f" ({offre.configuration.duree_mois} mois)"
        )
        payload = {
            "title": titre,
            "value": valeur,
            "currency": "EUR",
            "add_time": offre.date_generation.strftime("%Y-%m-%d %H:%M:%S"),
            # Rappel : pas de secret dans l'en-tête `User-Agent` ni dans le
            # payload — le token d'API passe en query string, comme imposé
            # par Pipedrive v1.
        }
        try:
            r = httpx.post(
                f"{self._base_url}/deals",
                params={"api_token": self._api_token},
                json=payload,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            return PipedriveResultat(None, None, "echec", f"Erreur réseau : {exc}")

        if r.status_code >= 400:
            return PipedriveResultat(None, None, "echec", f"HTTP {r.status_code} : {r.text[:200]}")

        corps = r.json()
        donnees = corps.get("data") if isinstance(corps, dict) else None
        if not isinstance(donnees, dict):
            return PipedriveResultat(None, None, "echec", "Réponse Pipedrive sans data")

        deal_id = donnees.get("id")
        if not isinstance(deal_id, int):
            return PipedriveResultat(None, None, "echec", "ID du deal manquant")

        return PipedriveResultat(
            deal_id=deal_id,
            deal_url=f"https://{self._base_url.split('//', 1)[1].rsplit('/v1', 1)[0]}/deal/{deal_id}",
            statut="pousse",
        )
