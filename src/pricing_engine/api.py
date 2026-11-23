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
from fastapi import UploadFile, File

from .users import (
    DUREE_SESSION_SECONDES,
    InMemorySessionStore,
    InMemoryUserStore,
    Role,
    Utilisateur,
    hacher_mot_de_passe,
    verifier_mot_de_passe,
)
from .catalog.api import build_catalog_router
from .catalog.seed import seed_catalog_akiem
from .catalog.store import CatalogStore, InMemoryCatalogStore
from .assistant import AnthropicAssistant, Assistant, Message as MessageAssistant, ScriptedAssistant
from .csv_import import (
    detecter_type_import,
    importer_budget_plan,
    importer_flotte,
    importer_grille_dry_lease,
)
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


# ---------------- Store utilisateurs + sessions ----------------

_users = InMemoryUserStore()
_sessions = InMemorySessionStore()


def _seeder_utilisateurs_par_defaut() -> None:
    """Crée les comptes de démo au démarrage. En vrai, on lira la liste
    depuis Entra ID / un store persistant ; ici c'est pour que la plateforme
    marche en local tout de suite."""
    defauts = [
        ("admin@akiem.com", "Admin Akiem", Role.ADMIN, "admin"),
        ("direction@akiem.com", "Direction", Role.DIRECTION, "direction"),
        ("head@akiem.com", "Head of Pricing", Role.PRICING, "pricing"),
        ("manager@akiem.com", "Manager", Role.PRICING, "pricing"),
        ("kam1@akiem.com", "KAM France", Role.KAM, "kam"),
        ("kam2@akiem.com", "KAM Allemagne", Role.KAM, "kam"),
        ("kam3@akiem.com", "KAM Pologne", Role.KAM, "kam"),
    ]
    for email, nom, role, mdp in defauts:
        if _users.get(email) is None:
            _users.creer(Utilisateur(
                email=email, nom=nom, role=role,
                hash_mot_de_passe=hacher_mot_de_passe(mdp),
            ))


_seeder_utilisateurs_par_defaut()

# ---------------- Catalogue PricingHub (Lot 1) ----------------

_catalog_store: CatalogStore = InMemoryCatalogStore()
# Seed du catalogue au démarrage — pour que l'API soit utilisable
# immédiatement en dev sans import CSV manuel.
seed_catalog_akiem(_catalog_store)


def get_catalog_store() -> CatalogStore:
    return _catalog_store


def get_users():
    return _users


def get_sessions():
    return _sessions


def get_current_user(
    authorization: str = Header(default="", description="Bearer <token>"),
    x_utilisateur: str = Header(default="", description="(Compat) e-mail direct, sans auth"),
) -> Utilisateur:
    """Résout l'utilisateur courant :
    - en priorité par `Authorization: Bearer <token>` (session login)
    - repli sur `X-Utilisateur: email@...` (compat scripts / tests)

    Pour le repli X-Utilisateur, on crée un faux utilisateur avec rôle
    KAM si l'e-mail n'existe pas dans le store. Ça garde l'API testable
    sans login explicite pour les scripts seed."""
    if authorization.startswith("Bearer "):
        token = authorization[7:]
        session = _sessions.get(token)
        if session is None:
            raise HTTPException(status_code=401, detail="Session invalide ou expirée")
        utilisateur = _users.get(session.email)
        if utilisateur is None or not utilisateur.actif:
            raise HTTPException(status_code=401, detail="Utilisateur désactivé")
        return utilisateur

    if x_utilisateur:
        existant = _users.get(x_utilisateur)
        if existant is not None:
            return existant
        # Mode compat : e-mail inconnu → utilisateur jetable KAM
        return Utilisateur(
            email=x_utilisateur, nom=x_utilisateur, role=Role.KAM,
            hash_mot_de_passe="", actif=True,
        )

    # Mode strict (production) : auth obligatoire, activé par REQUIRE_AUTH=1
    if os.environ.get("REQUIRE_AUTH", "").lower() in ("1", "true", "yes"):
        raise HTTPException(status_code=401, detail="Authentification requise")
    # Mode dev / compat tests : utilisateur anonyme ADMIN (voit tout)
    return Utilisateur(
        email="anonymous@akiem.local", nom="Anonymous (dev)", role=Role.ADMIN,
        hash_mot_de_passe="", actif=True,
    )


def exiger_permission(permission: str):
    """Dépendance qui refuse les utilisateurs sans la permission."""
    def _verifier(utilisateur: Utilisateur = Depends(get_current_user)) -> Utilisateur:
        if not utilisateur.a_permission(permission):
            raise HTTPException(status_code=403, detail=f"Permission '{permission}' refusée")
        return utilisateur
    return _verifier


# Monte le router catalogue PricingHub (Lot 1 : référentiel locomotive).
# Doit être après `get_catalog_store` et `exiger_permission`.
app.include_router(build_catalog_router(get_catalog_store, exiger_permission))


def get_utilisateur(utilisateur: Utilisateur = Depends(get_current_user)) -> str:
    """Compat : retourne l'e-mail de l'utilisateur courant (résolu par
    token Bearer, header X-Utilisateur ou fallback anonyme en mode dev
    quand REQUIRE_AUTH n'est pas défini)."""
    return utilisateur.email


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


# ---------------- Endpoints Auth ----------------


class _LoginRequest(BaseModel):
    email: str
    mot_de_passe: str


class _ChangePasswordRequest(BaseModel):
    ancien_mot_de_passe: str
    nouveau_mot_de_passe: str


class _CreateUserRequest(BaseModel):
    email: str
    nom: str
    role: Role
    mot_de_passe: str


@app.post("/api/v1/auth/login")
def login(body: _LoginRequest) -> dict:
    """Vérifie le mot de passe, ouvre une session, renvoie un token Bearer."""
    utilisateur = _users.get(body.email)
    if utilisateur is None or not utilisateur.actif:
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    if not verifier_mot_de_passe(body.mot_de_passe, utilisateur.hash_mot_de_passe):
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    session = _sessions.creer(utilisateur.email)
    return {
        "token": session.token,
        "duree_secondes": DUREE_SESSION_SECONDES,
        "utilisateur": {
            "email": utilisateur.email,
            "nom": utilisateur.nom,
            "role": utilisateur.role.value,
            "permissions": sorted(list(__import__("pricing_engine.users", fromlist=["PERMISSIONS"]).PERMISSIONS.get(utilisateur.role, set()))),
        },
    }


@app.get("/api/v1/auth/me")
def me(utilisateur: Utilisateur = Depends(get_current_user)) -> dict:
    from .users import PERMISSIONS
    return {
        "email": utilisateur.email,
        "nom": utilisateur.nom,
        "role": utilisateur.role.value,
        "permissions": sorted(list(PERMISSIONS.get(utilisateur.role, set()))),
    }


@app.post("/api/v1/auth/logout")
def logout(authorization: str = Header(default="")) -> dict:
    if authorization.startswith("Bearer "):
        _sessions.revoquer(authorization[7:])
    return {"ok": True}


@app.post("/api/v1/auth/change-password")
def changer_mot_de_passe(
    body: _ChangePasswordRequest,
    utilisateur: Utilisateur = Depends(get_current_user),
) -> dict:
    if not verifier_mot_de_passe(body.ancien_mot_de_passe, utilisateur.hash_mot_de_passe):
        raise HTTPException(status_code=401, detail="Ancien mot de passe incorrect")
    if len(body.nouveau_mot_de_passe) < 6:
        raise HTTPException(status_code=422, detail="Nouveau mot de passe trop court (min 6)")
    utilisateur.hash_mot_de_passe = hacher_mot_de_passe(body.nouveau_mot_de_passe)
    _users.mettre_a_jour(utilisateur)
    _sessions.revoquer_pour(utilisateur.email)  # force relogin partout
    return {"ok": True}


@app.get("/api/v1/utilisateurs")
def lister_utilisateurs(_: Utilisateur = Depends(exiger_permission("gerer_utilisateurs"))) -> list[dict]:
    return [
        {"email": u.email, "nom": u.nom, "role": u.role.value, "actif": u.actif}
        for u in _users.lister()
    ]


@app.post("/api/v1/utilisateurs")
def creer_utilisateur(
    body: _CreateUserRequest,
    _: Utilisateur = Depends(exiger_permission("gerer_utilisateurs")),
) -> dict:
    if _users.get(body.email) is not None:
        raise HTTPException(status_code=409, detail="E-mail déjà pris")
    if len(body.mot_de_passe) < 6:
        raise HTTPException(status_code=422, detail="Mot de passe trop court (min 6)")
    nouveau = Utilisateur(
        email=body.email, nom=body.nom, role=body.role,
        hash_mot_de_passe=hacher_mot_de_passe(body.mot_de_passe),
    )
    _users.creer(nouveau)
    return {"email": nouveau.email, "nom": nouveau.nom, "role": nouveau.role.value}


@app.delete("/api/v1/utilisateurs/{email}", status_code=204)
def supprimer_utilisateur(
    email: str,
    courant: Utilisateur = Depends(exiger_permission("gerer_utilisateurs")),
):
    if email.lower() == courant.email.lower():
        raise HTTPException(status_code=409, detail="Impossible de supprimer son propre compte")
    if not _users.supprimer(email):
        raise HTTPException(status_code=404, detail="Utilisateur inconnu")
    _sessions.revoquer_pour(email)
    return Response(status_code=204)


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
def lister_les_derogations(
    derogations: DerogationStore = Depends(get_derogations),
    utilisateur: Utilisateur = Depends(get_current_user),
) -> list[Derogation]:
    """Registre central des dérogations (M4-05). Filtré sur les demandes
    du KAM si rôle=KAM ; voit tout si rôle=PRICING/DIRECTION/ADMIN."""
    toutes = derogations.lister()
    if utilisateur.a_permission("voir_toutes_derogations"):
        return toutes
    email = utilisateur.email.lower()
    return [d for d in toutes if d.demandeur.lower() == email]


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
    utilisateur: Utilisateur = Depends(get_current_user),
) -> list[OffreGeneree]:
    """Journal des offres générées. Filtré sur les offres du KAM courant
    si rôle=KAM ; voit tout si rôle=PRICING/DIRECTION/ADMIN."""
    toutes = offres_generees.lister()
    if utilisateur.a_permission("voir_toutes_offres"):
        return toutes
    email = utilisateur.email.lower()
    return [o for o in toutes if o.utilisateur.lower() == email]


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


@app.post("/api/v1/referentiel/brouillons/{numero}/import/dry-lease-grille")
async def importer_grille_dl(
    numero: int,
    fichier: UploadFile = File(..., description="CSV avec en-tête : serie_code, duree_min_mois, duree_max_mois, loyer_mensuel"),
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
) -> dict:
    """Import en masse de la grille Dry lease. Remplace entièrement la
    grille du brouillon (comme un PUT) ; les lignes en erreur sont
    collectées et renvoyées sans bloquer les autres."""
    draft = _brouillon_ou_404(referentiel, numero)
    contenu = (await fichier.read()).decode("utf-8", errors="replace")
    resultat = importer_grille_dry_lease(contenu)
    if resultat.nb_lignes_importees > 0:
        avant = list(draft.grille_dry_lease)
        draft.grille_dry_lease = resultat.grille_dry_lease
        referentiel.enregistrer_modification(
            draft, "grille_dry_lease", "import_csv", avant, resultat.grille_dry_lease,
            utilisateur, f"Import CSV ({resultat.nb_lignes_importees} lignes)",
        )
    return {
        "nb_lignes_lues": resultat.nb_lignes_lues,
        "nb_lignes_importees": resultat.nb_lignes_importees,
        "erreurs": resultat.erreurs,
    }


@app.post("/api/v1/referentiel/brouillons/{numero}/import/budget-plan")
async def importer_bp(
    numero: int,
    fichier: UploadFile = File(..., description="CSV avec en-tête : serie_code, km_min, km_max, bp_hm, bp_om, exercice"),
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
) -> dict:
    """Import en masse du Budget Plan (BP HM + BP OM). Déduit également
    les tranches de km et remplace celles du brouillon."""
    draft = _brouillon_ou_404(referentiel, numero)
    contenu = (await fichier.read()).decode("utf-8", errors="replace")
    resultat = importer_budget_plan(contenu)
    if resultat.nb_lignes_importees > 0:
        avant_bp = list(draft.budget_plan)
        avant_tranches = list(draft.tranches_km)
        draft.budget_plan = resultat.budget_plan
        draft.tranches_km = resultat.tranches_km
        referentiel.enregistrer_modification(
            draft, "budget_plan", "import_csv", avant_bp, resultat.budget_plan,
            utilisateur, f"Import CSV BP ({resultat.nb_lignes_importees} lignes)",
        )
        referentiel.enregistrer_modification(
            draft, "tranches_km", "import_csv", avant_tranches, resultat.tranches_km,
            utilisateur, "Dérivées du BP importé",
        )
    return {
        "nb_lignes_lues": resultat.nb_lignes_lues,
        "nb_lignes_importees": resultat.nb_lignes_importees,
        "nb_tranches_km_deduites": len(resultat.tranches_km),
        "erreurs": resultat.erreurs,
    }


@app.post("/api/v1/referentiel/brouillons/{numero}/import/flotte")
async def importer_locomotives(
    numero: int,
    fichier: UploadFile = File(..., description="CSV avec en-tête : numero, produit, sous_serie, serie_code, homologations, mise_en_service, km_cumules, statut"),
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
    remplacer: bool = False,
) -> dict:
    """Import en masse de la flotte. Par défaut, ajoute aux locos
    existantes (met à jour si le numéro existe déjà) ; `remplacer=true`
    écrase complètement la flotte du brouillon."""
    draft = _brouillon_ou_404(referentiel, numero)
    contenu = (await fichier.read()).decode("utf-8", errors="replace")
    resultat = importer_flotte(contenu)
    if resultat.nb_lignes_importees > 0:
        avant = dict(draft.flotte)
        if remplacer:
            draft.flotte = {l.numero: l for l in resultat.locomotives}
        else:
            for l in resultat.locomotives:
                draft.flotte[l.numero] = l
        action = "import_csv_remplacement" if remplacer else "import_csv_fusion"
        referentiel.enregistrer_modification(
            draft, "flotte", action, avant, dict(draft.flotte),
            utilisateur, f"Import CSV flotte ({resultat.nb_lignes_importees} lignes)",
        )
    return {
        "nb_lignes_lues": resultat.nb_lignes_lues,
        "nb_lignes_importees": resultat.nb_lignes_importees,
        "erreurs": resultat.erreurs,
    }


@app.post("/api/v1/referentiel/brouillons/{numero}/import/auto")
async def importer_auto_detection(
    numero: int,
    fichier: UploadFile = File(..., description="N'importe lequel des 3 CSV (DL, BP, Flotte) — le type est détecté par les colonnes de l'en-tête."),
    utilisateur: str = Depends(get_utilisateur),
    referentiel: Referentiel = Depends(get_referentiel),
    remplacer: bool = False,
) -> dict:
    """Import CSV avec auto-détection du type : lit l'en-tête, décide s'il
    s'agit d'une grille Dry lease, d'un Budget Plan ou d'une Flotte, et
    aiguille vers l'import correspondant. Accepte les séparateurs `,` et
    `;` (Excel francophone), le BOM UTF-8 et la virgule décimale."""
    draft = _brouillon_ou_404(referentiel, numero)
    contenu = (await fichier.read()).decode("utf-8", errors="replace")

    type_detecte = detecter_type_import(contenu)
    if type_detecte is None:
        return {
            "type_detecte": None,
            "nb_lignes_lues": 0,
            "nb_lignes_importees": 0,
            "erreurs": [
                "Type de CSV non reconnu. Colonnes attendues : "
                "grille DL (serie_code, duree_*, loyer_mensuel) / "
                "BP (serie_code, km_*, bp_hm, bp_om) / "
                "Flotte (numero, produit, homologations, …)."
            ],
        }

    if type_detecte == "dry-lease-grille":
        r = importer_grille_dry_lease(contenu)
        if r.nb_lignes_importees > 0:
            avant = list(draft.grille_dry_lease)
            draft.grille_dry_lease = r.grille_dry_lease
            referentiel.enregistrer_modification(
                draft, "grille_dry_lease", "import_csv", avant, r.grille_dry_lease,
                utilisateur, f"Import CSV auto-détecté ({r.nb_lignes_importees} lignes)",
            )
        return {
            "type_detecte": type_detecte,
            "nb_lignes_lues": r.nb_lignes_lues,
            "nb_lignes_importees": r.nb_lignes_importees,
            "erreurs": r.erreurs,
        }

    if type_detecte == "budget-plan":
        r = importer_budget_plan(contenu)
        if r.nb_lignes_importees > 0:
            avant_bp, avant_tr = list(draft.budget_plan), list(draft.tranches_km)
            draft.budget_plan = r.budget_plan
            draft.tranches_km = r.tranches_km
            referentiel.enregistrer_modification(
                draft, "budget_plan", "import_csv", avant_bp, r.budget_plan,
                utilisateur, f"Import CSV auto-détecté ({r.nb_lignes_importees} lignes)",
            )
            referentiel.enregistrer_modification(
                draft, "tranches_km", "import_csv", avant_tr, r.tranches_km,
                utilisateur, "Dérivées du BP importé",
            )
        return {
            "type_detecte": type_detecte,
            "nb_lignes_lues": r.nb_lignes_lues,
            "nb_lignes_importees": r.nb_lignes_importees,
            "nb_tranches_km_deduites": len(r.tranches_km),
            "erreurs": r.erreurs,
        }

    # flotte
    r = importer_flotte(contenu)
    if r.nb_lignes_importees > 0:
        avant = dict(draft.flotte)
        if remplacer:
            draft.flotte = {l.numero: l for l in r.locomotives}
        else:
            for l in r.locomotives:
                draft.flotte[l.numero] = l
        action = "import_csv_remplacement" if remplacer else "import_csv_fusion"
        referentiel.enregistrer_modification(
            draft, "flotte", action, avant, dict(draft.flotte),
            utilisateur, f"Import CSV auto-détecté ({r.nb_lignes_importees} lignes)",
        )
    return {
        "type_detecte": type_detecte,
        "nb_lignes_lues": r.nb_lignes_lues,
        "nb_lignes_importees": r.nb_lignes_importees,
        "erreurs": r.erreurs,
    }


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
