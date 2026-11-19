"""API du moteur de prix (M2-06) et administration minimale du référentiel.

Cette API est la seule porte d'entrée vers la logique de prix : elle sera
appelée à l'identique par le configurateur KAM (Power Apps), Power BI et
l'agent IA (cf. section 4, architecture cible). L'administration du
référentiel exposée ici (brouillon / contrôles qualité / publication) est
une version minimale ; en cible, la saisie se fait dans Dataverse.
"""

from __future__ import annotations

from fastapi import Body, Depends, FastAPI, Header, HTTPException

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
from .referentiel import AnomalieControleQualite, Referentiel, StatutVersion

app = FastAPI(
    title="Akiem Pricing — Moteur de prix",
    description="API du moteur de prix full service leasing (Lot 1 — Socle).",
    version="0.1.0",
)

_referentiel = Referentiel()


def get_referentiel() -> Referentiel:
    return _referentiel


def get_utilisateur(x_utilisateur: str = Header(..., description="E-mail de l'utilisateur")) -> str:
    return x_utilisateur


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
        numero, "series", "set", avant, serie, utilisateur, raison
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
        numero, "tranches_km", "set", avant, tranches, utilisateur, "Mise à jour tranches de km"
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
        numero, "grille_dry_lease", "set", avant, grille, utilisateur, "Mise à jour grille Dry lease"
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
        numero, "budget_plan", "set", avant, bp, utilisateur, "Mise à jour BP HM/OM"
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
        numero, "clients", "set", avant, client, utilisateur, "Mise à jour client"
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
        numero, "flotte", "set", avant, locomotive, utilisateur, "Mise à jour locomotive"
    )
    return locomotive


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
        numero, "delegations", "set", avant, delegations, utilisateur, "Mise à jour délégations"
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
        numero, "parametres", "set", avant, parametres, utilisateur, "Mise à jour paramètres"
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
            "horodatage": e.horodatage,
            "utilisateur": e.utilisateur,
            "table": e.table,
            "action": e.action,
            "raison": e.raison,
            "valide_par": e.valide_par,
        }
        for e in referentiel.journal
    ]


def _brouillon_ou_404(referentiel: Referentiel, numero: int):
    try:
        draft = referentiel.version(numero)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Version inconnue") from exc
    if draft.statut != StatutVersion.BROUILLON:
        raise HTTPException(status_code=409, detail="Cette version n'est plus un brouillon")
    return draft
