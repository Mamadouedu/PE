"""API du moteur de prix (M2-06) et administration minimale du référentiel.

Cette API est la seule porte d'entrée vers la logique de prix : elle sera
appelée à l'identique par le configurateur KAM (application web), Power
Automate et l'agent IA (version sur mesure, sans Power Apps). L'administration
du référentiel exposée ici (brouillon / contrôles qualité / publication) est
une version minimale, destinée à être remplacée par un vrai configurateur.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .derogation import (
    DecisionInvalide,
    Derogation,
    DerogationNonNecessaire,
    DerogationStore,
    InMemoryDerogationStore,
    StatutDerogation,
    decider_derogation,
    demander_derogation,
)
from .engine import calculer_offre, validateur_requis
from .models import (
    BudgetPlanEntry,
    Client,
    ConfigurationOffre,
    DetailOffre,
    GrilleDryLeaseEntry,
    Locomotive,
    Parametres,
    Serie,
    TrancheKm,
    Validateur,
)
from .assistant import AnthropicAssistant, Assistant, Message as MessageAssistant, ScriptedAssistant
from .offre_pdf import InMemoryOffreGenereeStore, OffreGeneree, OffreGenereeStore, generer_offre
from .pipedrive import HttpPipedriveBridge, NoOpPipedriveBridge, PipedriveBridge
from .referentiel import AnomalieControleQualite, Referentiel, StatutVersion

app = FastAPI(
    title="Akiem Pricing — Moteur de prix",
    description="API du moteur de prix full service leasing (Lot 1 — Socle).",
    version="0.1.0",
    docs_url=None,
)

# CORS : origines du frontend (configurateur KAM) autorisées à appeler cette
# API. En dev, le serveur Vite par défaut ; en production, à restreindre au
# domaine réel via CORS_ORIGINS (liste séparée par des virgules).
_cors_origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Sans ça, le JS du frontend ne peut pas lire Content-Disposition (donc
    # pas le numéro d'offre dans le nom du fichier téléchargé) : les
    # navigateurs n'exposent par défaut qu'une courte liste d'en-têtes de
    # réponse aux requêtes cross-origin, celui-ci n'en fait pas partie.
    expose_headers=["Content-Disposition"],
)

# Documentation interactive servie en local (pas de CDN) : de nombreux
# réseaux d'entreprise, comme celui qui a motivé ce cahier, bloquent les CDN
# publics. Mêmes assets que ceux que FastAPI pointe par défaut (jsdelivr),
# juste rapatriés dans static_vendor/ (voir swagger-ui/README dans ce dossier).
_SWAGGER_DIR = Path(__file__).parent / "static_vendor" / "swagger-ui"
app.mount("/static/swagger-ui", StaticFiles(directory=str(_SWAGGER_DIR)), name="swagger-ui-static")


@app.get("/docs", include_in_schema=False)
def documentation_interactive():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} — Docs",
        swagger_js_url="/static/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui/swagger-ui.css",
    )


def _build_referentiel() -> Referentiel:
    """Backend PostgreSQL si `DATABASE_URL` est défini (version sur mesure,
    sans Dataverse) ; sinon un backend en mémoire, pratique en local et pour
    les tests qui ne portent pas sur la persistance."""

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return Referentiel()

    from .db import SqlAlchemyReferentielBackend, make_session_factory

    return Referentiel(SqlAlchemyReferentielBackend(make_session_factory(database_url)))


_referentiel = _build_referentiel()


def get_referentiel() -> Referentiel:
    return _referentiel


def _build_derogation_store() -> DerogationStore:
    """Même principe que `_build_referentiel` : PostgreSQL si `DATABASE_URL`
    est défini, sinon un registre en mémoire."""

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return InMemoryDerogationStore()

    from .db import SqlAlchemyDerogationStore, make_session_factory

    return SqlAlchemyDerogationStore(make_session_factory(database_url))


_derogations = _build_derogation_store()


def get_derogations() -> DerogationStore:
    return _derogations


def _build_offres_generees_store() -> OffreGenereeStore:
    """Même principe que `_build_referentiel` : PostgreSQL si `DATABASE_URL`
    est défini, sinon un registre en mémoire (la numérotation repart alors
    de 1 à chaque redémarrage — sans conséquence en dev/test)."""

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return InMemoryOffreGenereeStore()

    from .db import SqlAlchemyOffreGenereeStore, make_session_factory

    return SqlAlchemyOffreGenereeStore(make_session_factory(database_url))


_offres_generees = _build_offres_generees_store()


def get_offres_generees() -> OffreGenereeStore:
    return _offres_generees


def _build_pipedrive_bridge() -> PipedriveBridge:
    """Bridge Pipedrive (M3-06). Actif dès que `PIPEDRIVE_API_TOKEN` et
    `PIPEDRIVE_COMPANY_DOMAIN` sont définis ; sinon NoOp pour laisser
    l'API tourner en local sans CRM."""
    token = os.environ.get("PIPEDRIVE_API_TOKEN")
    domain = os.environ.get("PIPEDRIVE_COMPANY_DOMAIN")
    if token and domain:
        return HttpPipedriveBridge(api_token=token, company_domain=domain)
    return NoOpPipedriveBridge()


_pipedrive = _build_pipedrive_bridge()


def get_pipedrive() -> PipedriveBridge:
    return _pipedrive


def _build_assistant() -> Assistant:
    """Assistant conversationnel (M3-08). AnthropicAssistant si une clé API
    est présente, sinon ScriptedAssistant (répond aux mots-clés usuels)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
        return AnthropicAssistant(api_key=api_key, model=model)
    return ScriptedAssistant()


_assistant = _build_assistant()


def get_assistant() -> Assistant:
    return _assistant


def get_utilisateur(x_utilisateur: str = Header(..., description="E-mail de l'utilisateur")) -> str:
    return x_utilisateur


def verifier_secret_webhook(
    x_webhook_secret: str = Header(default="", description="Secret partagé avec Power Automate"),
) -> None:
    """Protège le webhook entrant (décision de dérogation) : sans secret
    configuré, l'endpoint refuse tout appel plutôt que de l'accepter sans
    vérification."""

    secret_attendu = os.environ.get("POWER_AUTOMATE_CALLBACK_SECRET")
    if not secret_attendu:
        raise HTTPException(
            status_code=501, detail="POWER_AUTOMATE_CALLBACK_SECRET n'est pas configuré"
        )
    if x_webhook_secret != secret_attendu:
        raise HTTPException(status_code=403, detail="Secret invalide")


class DemandeDerogationRequest(BaseModel):
    configuration: ConfigurationOffre
    justification: str = Field(min_length=1)


class DecisionDerogationRequest(BaseModel):
    decision: Literal["approuvee", "rejetee"]
    decideur: str
    commentaire: str | None = None


@app.post("/api/v1/prix", response_model=DetailOffre)
def chiffrer_offre(
    config: ConfigurationOffre, referentiel: Referentiel = Depends(get_referentiel)
) -> DetailOffre:
    """Calcule le prix d'une configuration sur la version publiée du référentiel (M2-01 à M2-05)."""

    version = referentiel.version_publiee()
    if version is None:
        raise HTTPException(status_code=409, detail="Aucune version du référentiel n'est publiée")
    try:
        return calculer_offre(version, config)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/derogations", response_model=Derogation)
def demander_une_derogation(
    demande: DemandeDerogationRequest,
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
    derogations: DerogationStore = Depends(get_derogations),
) -> Derogation:
    """Crée une demande de dérogation (M4-02 : justification obligatoire).

    Le niveau et le validateur sont recalculés ici, jamais transmis par le
    client (M4-01) : voir `derogation.demander_derogation`. Déclenche un
    webhook best-effort vers Power Automate si `POWER_AUTOMATE_WEBHOOK_URL`
    est défini (M4-03).
    """

    version = referentiel.version_publiee()
    if version is None:
        raise HTTPException(status_code=409, detail="Aucune version du référentiel n'est publiée")
    try:
        return demander_derogation(
            derogations, version, demande.configuration, demande.justification, utilisateur
        )
    except DerogationNonNecessaire as exc:
        raise HTTPException(
            status_code=400, detail="Cette offre est dans les règles : aucune dérogation nécessaire"
        ) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/derogations", response_model=list[Derogation])
def lister_les_derogations(derogations: DerogationStore = Depends(get_derogations)) -> list[Derogation]:
    """Le registre central des dérogations (M4-05)."""

    return derogations.lister()


@app.get("/api/v1/derogations/{id_}", response_model=Derogation)
def obtenir_une_derogation(
    id_: int, derogations: DerogationStore = Depends(get_derogations)
) -> Derogation:
    try:
        return derogations.obtenir(id_)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dérogation inconnue") from exc


@app.post(
    "/api/v1/derogations/{id_}/decision",
    response_model=Derogation,
    dependencies=[Depends(verifier_secret_webhook)],
)
def decider_une_derogation(
    id_: int,
    decision: DecisionDerogationRequest,
    derogations: DerogationStore = Depends(get_derogations),
) -> Derogation:
    """Webhook entrant : la décision prise dans Teams, relayée par Power
    Automate. Protégé par `POWER_AUTOMATE_CALLBACK_SECRET` (en-tête
    `X-Webhook-Secret`)."""

    try:
        return decider_derogation(
            derogations,
            id_,
            StatutDerogation(decision.decision),
            decision.decideur,
            decision.commentaire,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dérogation inconnue") from exc
    except DecisionInvalide as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/offres/pdf")
def generer_l_offre_pdf(
    config: ConfigurationOffre,
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
    offres_generees: OffreGenereeStore = Depends(get_offres_generees),
    pipedrive: PipedriveBridge = Depends(get_pipedrive),
) -> Response:
    """Génère l'offre PDF numérotée (M3-05). Le PDF ne montre que le prix
    retenu par brique — jamais le catalogue ni le plancher (ça révélerait la
    marge de négociation au client), ni les contrôles internes. Porte la
    mention PROJET tant que `niveau_validation > 0`. Chaque génération est
    journalisée (M3-06, la part « journal des offres »), et un deal est
    poussé dans Pipedrive si l'intégration est configurée (M3-06, part
    « écriture du deal »)."""

    version = referentiel.version_publiee()
    if version is None:
        raise HTTPException(status_code=409, detail="Aucune version du référentiel n'est publiée")
    try:
        offre, pdf_bytes = generer_offre(offres_generees, version, config, utilisateur, pipedrive=pipedrive)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="offre-{offre.numero}.pdf"'},
    )


@app.get("/api/v1/offres", response_model=list[OffreGeneree])
def lister_les_offres_generees(
    offres_generees: OffreGenereeStore = Depends(get_offres_generees),
) -> list[OffreGeneree]:
    """Journal des offres générées (M3-06, part « journal » — l'écriture
    dans Pipedrive reste à faire)."""

    return offres_generees.lister()


@app.get("/api/v1/referentiel/publiee")
def version_publiee(referentiel: Referentiel = Depends(get_referentiel)) -> dict:
    version = referentiel.version_publiee()
    if version is None:
        raise HTTPException(status_code=404, detail="Aucune version publiée")
    return {
        "numero": version.numero,
        "date_publication": version.date_publication,
        "publie_par": version.publie_par,
        "nb_series": len(version.series),
        "nb_clients": len(version.clients),
        "nb_locomotives": len(version.flotte),
    }


def _version_to_dict(v) -> dict:
    """Serialise une VersionReferentiel pour le JSON (admin UI)."""
    return {
        "numero": v.numero,
        "statut": v.statut.value,
        "date_creation": v.date_creation.isoformat() if v.date_creation else None,
        "date_publication": v.date_publication.isoformat() if v.date_publication else None,
        "publie_par": v.publie_par,
        "series": {k: s.model_dump() for k, s in v.series.items()},
        "tranches_km": [t.model_dump() for t in v.tranches_km],
        "grille_dry_lease": [g.model_dump() for g in v.grille_dry_lease],
        "budget_plan": [b.model_dump() for b in v.budget_plan],
        "clients": {k: c.model_dump() for k, c in v.clients.items()},
        "flotte": {k: l.model_dump() for k, l in v.flotte.items()},
        "parametres": v.parametres.model_dump(),
        "delegations": [d.model_dump() for d in v.delegations],
    }


@app.get("/api/v1/referentiel/brouillons")
def lister_brouillons(referentiel: Referentiel = Depends(get_referentiel)) -> list[dict]:
    """Liste toutes les versions du référentiel (brouillons, publiées,
    archivées) avec leurs compteurs — pour l'admin UI."""
    return [
        {
            "numero": v.numero,
            "statut": v.statut.value,
            "date_creation": v.date_creation.isoformat() if v.date_creation else None,
            "date_publication": v.date_publication.isoformat() if v.date_publication else None,
            "publie_par": v.publie_par,
            "nb_series": len(v.series),
            "nb_clients": len(v.clients),
            "nb_locomotives": len(v.flotte),
            "nb_tranches_km": len(v.tranches_km),
            "nb_grille_dl": len(v.grille_dry_lease),
            "nb_budget_plan": len(v.budget_plan),
            "nb_delegations": len(v.delegations),
        }
        for v in sorted(referentiel.versions(), key=lambda x: x.numero, reverse=True)
    ]


@app.get("/api/v1/referentiel/brouillons/{numero}")
def obtenir_brouillon(numero: int, referentiel: Referentiel = Depends(get_referentiel)) -> dict:
    """Retourne le contenu complet d'une version du référentiel."""
    try:
        v = referentiel.version(numero)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Version {numero} inconnue")
    return _version_to_dict(v)


@app.post("/api/v1/referentiel/brouillons")
def creer_brouillon(referentiel: Referentiel = Depends(get_referentiel)) -> dict:
    draft = referentiel.nouveau_brouillon()
    return {"numero": draft.numero, "statut": draft.statut.value}


@app.put("/api/v1/referentiel/brouillons/{numero}/series/{code}")
def definir_serie(
    numero: int,
    code: str,
    serie: Serie,
    utilisateur: str = Depends(get_utilisateur),
    raison: str = Body(embed=True, default="Mise à jour série"),
    referentiel: Referentiel = Depends(get_referentiel),
) -> Serie:
    draft = _brouillon_ou_404(referentiel, numero)
    avant = draft.series.get(code)
    draft.series[code] = serie
    referentiel.enregistrer_modification(
        draft, "series", "set", avant, serie, utilisateur, raison
    )
    return serie


@app.put("/api/v1/referentiel/brouillons/{numero}/tranches-km")
def definir_tranches_km(
    numero: int,
    tranches: list[TrancheKm],
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
) -> list[TrancheKm]:
    draft = _brouillon_ou_404(referentiel, numero)
    avant = list(draft.tranches_km)
    draft.tranches_km = tranches
    referentiel.enregistrer_modification(
        draft, "tranches_km", "set", avant, tranches, utilisateur, "Mise à jour tranches de km"
    )
    return tranches


@app.put("/api/v1/referentiel/brouillons/{numero}/grille-dry-lease")
def definir_grille_dry_lease(
    numero: int,
    grille: list[GrilleDryLeaseEntry],
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
) -> list[GrilleDryLeaseEntry]:
    draft = _brouillon_ou_404(referentiel, numero)
    avant = list(draft.grille_dry_lease)
    draft.grille_dry_lease = grille
    referentiel.enregistrer_modification(
        draft, "grille_dry_lease", "set", avant, grille, utilisateur, "Mise à jour grille Dry lease"
    )
    return grille


@app.put("/api/v1/referentiel/brouillons/{numero}/budget-plan")
def definir_budget_plan(
    numero: int,
    bp: list[BudgetPlanEntry],
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
) -> list[BudgetPlanEntry]:
    draft = _brouillon_ou_404(referentiel, numero)
    avant = list(draft.budget_plan)
    draft.budget_plan = bp
    referentiel.enregistrer_modification(
        draft, "budget_plan", "set", avant, bp, utilisateur, "Mise à jour BP HM/OM"
    )
    return bp


@app.put("/api/v1/referentiel/brouillons/{numero}/clients/{code}")
def definir_client(
    numero: int,
    code: str,
    client: Client,
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
) -> Client:
    draft = _brouillon_ou_404(referentiel, numero)
    avant = draft.clients.get(code)
    draft.clients[code] = client
    referentiel.enregistrer_modification(
        draft, "clients", "set", avant, client, utilisateur, "Mise à jour client"
    )
    return client


@app.put("/api/v1/referentiel/brouillons/{numero}/flotte/{numero_loco}")
def definir_locomotive(
    numero: int,
    numero_loco: str,
    locomotive: Locomotive,
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
) -> Locomotive:
    draft = _brouillon_ou_404(referentiel, numero)
    avant = draft.flotte.get(numero_loco)
    draft.flotte[numero_loco] = locomotive
    referentiel.enregistrer_modification(
        draft, "flotte", "set", avant, locomotive, utilisateur, "Mise à jour locomotive"
    )
    return locomotive


@app.delete("/api/v1/referentiel/brouillons/{numero}/series/{code}", status_code=204)
def supprimer_serie(
    numero: int,
    code: str,
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
):
    draft = _brouillon_ou_404(referentiel, numero)
    avant = draft.series.pop(code, None)
    if avant is None:
        raise HTTPException(status_code=404, detail=f"Série {code} inconnue")
    referentiel.enregistrer_modification(
        draft, "series", "delete", avant, None, utilisateur, "Suppression série"
    )
    return Response(status_code=204)


@app.delete("/api/v1/referentiel/brouillons/{numero}/clients/{code}", status_code=204)
def supprimer_client(
    numero: int,
    code: str,
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
):
    draft = _brouillon_ou_404(referentiel, numero)
    avant = draft.clients.pop(code, None)
    if avant is None:
        raise HTTPException(status_code=404, detail=f"Client {code} inconnu")
    referentiel.enregistrer_modification(
        draft, "clients", "delete", avant, None, utilisateur, "Suppression client"
    )
    return Response(status_code=204)


@app.delete("/api/v1/referentiel/brouillons/{numero}/flotte/{numero_loco}", status_code=204)
def supprimer_locomotive(
    numero: int,
    numero_loco: str,
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
):
    draft = _brouillon_ou_404(referentiel, numero)
    avant = draft.flotte.pop(numero_loco, None)
    if avant is None:
        raise HTTPException(status_code=404, detail=f"Locomotive {numero_loco} inconnue")
    referentiel.enregistrer_modification(
        draft, "flotte", "delete", avant, None, utilisateur, "Suppression locomotive"
    )
    return Response(status_code=204)


@app.put("/api/v1/referentiel/brouillons/{numero}/delegations")
def definir_delegations(
    numero: int,
    delegations: list[Validateur],
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
) -> list[Validateur]:
    draft = _brouillon_ou_404(referentiel, numero)
    avant = list(draft.delegations)
    draft.delegations = delegations
    referentiel.enregistrer_modification(
        draft, "delegations", "set", avant, delegations, utilisateur, "Mise à jour délégations"
    )
    return delegations


@app.put("/api/v1/referentiel/brouillons/{numero}/parametres")
def definir_parametres(
    numero: int,
    parametres: Parametres,
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
) -> Parametres:
    draft = _brouillon_ou_404(referentiel, numero)
    avant = draft.parametres
    draft.parametres = parametres
    referentiel.enregistrer_modification(
        draft, "parametres", "set", avant, parametres, utilisateur, "Mise à jour paramètres"
    )
    return parametres


@app.get("/api/v1/referentiel/brouillons/{numero}/controles-qualite", response_model=list[AnomalieControleQualite])
def controles_qualite(numero: int, referentiel: Referentiel = Depends(get_referentiel)):
    draft = _brouillon_ou_404(referentiel, numero)
    return referentiel.controler_qualite(draft)


@app.post("/api/v1/referentiel/brouillons/{numero}/publier")
def publier(
    numero: int,
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
) -> dict:
    draft = _brouillon_ou_404(referentiel, numero)
    anomalies = referentiel.publier(numero, utilisateur)
    bloquant = any(a.bloquante for a in anomalies)
    if bloquant:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Publication bloquée : anomalie bloquante détectée",
                "anomalies": [a.model_dump() for a in anomalies],
            },
        )
    return {
        "numero": draft.numero,
        "statut": draft.statut.value,
        "anomalies_non_bloquantes": [a.model_dump() for a in anomalies],
    }


@app.get("/api/v1/referentiel/journal")
def journal(referentiel: Referentiel = Depends(get_referentiel)) -> list[dict]:
    return [
        {
            "version_numero": e.version_numero,
            "horodatage": e.horodatage,
            "utilisateur": e.utilisateur,
            "table": e.table,
            "action": e.action,
            "raison": e.raison,
            "valide_par": e.valide_par,
        }
        for e in referentiel.journal
    ]


class _AssistantMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class _AssistantChatRequest(BaseModel):
    messages: list[_AssistantMessageRequest]


@app.post("/api/v1/assistant/chat")
def assistant_chat(
    body: _AssistantChatRequest = Body(...),
    assistant: Assistant = Depends(get_assistant),
) -> dict:
    """Assistant conversationnel du KAM (M3-08). Historique conversationnel
    passé en entrée. Branche sur Anthropic si `ANTHROPIC_API_KEY`, sinon
    sur un fallback déterministe à base de mots-clés."""
    historique = [MessageAssistant(role=m.role, content=m.content) for m in body.messages]
    reponse = assistant.repondre(historique)
    return {"message": reponse.message, "moteur": reponse.moteur}


def _brouillon_ou_404(referentiel: Referentiel, numero: int):
    try:
        draft = referentiel.version(numero)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Version inconnue") from exc
    if draft.statut != StatutVersion.BROUILLON:
        raise HTTPException(status_code=409, detail="Cette version n'est plus un brouillon")
    return draft
