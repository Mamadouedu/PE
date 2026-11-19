"""Entités du référentiel pricing (cahier des charges, section 8.3).

Toutes les valeurs par défaut citées dans le cahier (section 6) sont reprises
ici comme valeurs par défaut des Paramètres ; elles restent modifiables sans
développement (M2-05), via une nouvelle version du référentiel.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Brique(str, Enum):
    DRY_LEASE = "DL"
    HEAVY_MAINTENANCE = "HM"
    OPERATION_MAINTENANCE = "OM"
    ASSURANCE = "ASSURANCE"


class Serie(BaseModel):
    """Série de locomotives (ex: Vectron, Traxx)."""

    code: str
    valeur_neuve: float = Field(gt=0, description="VN : valeur neuve en € HT")
    duree_vie_ans: float = Field(default=30.0, gt=0, description="L")
    vr_fin_vie_taux: float = Field(default=0.10, ge=0, le=1, description="v")
    km_reference_annuel: float = Field(gt=0, description="K_ref")
    cout_hm_8_ans: float = Field(ge=0, description="Coût de la révision des 8 ans")
    cout_hm_16_ans: float = Field(ge=0, description="Coût de la révision des 16 ans")
    om_fixe: float = Field(ge=0, description="Partie fixe de l'OM (€/an)")
    om_variable_eur_par_km: float = Field(ge=0, description="Partie variable de l'OM (€/km)")
    taux_assurance_annuel: float = Field(ge=0, description="Taux annuel d'assurance")

    @property
    def cout_hm_par_km(self) -> float:
        return (self.cout_hm_8_ans + self.cout_hm_16_ans) / (16 * self.km_reference_annuel)


class TrancheDuree(BaseModel):
    """Tranche de durée utilisée pour la grille Dry lease."""

    duree_min_mois: int = Field(ge=0)
    duree_max_mois: int | None = Field(default=None, description="None = pas de borne haute")

    def contient(self, duree_mois: int) -> bool:
        if duree_mois < self.duree_min_mois:
            return False
        return self.duree_max_mois is None or duree_mois <= self.duree_max_mois


class TrancheKm(BaseModel):
    """Tranche de kilométrage annuel (80 000 à 200 000 km) et ses coefficients."""

    km_min: int = Field(ge=0)
    km_max: int | None = Field(default=None, description="None = pas de borne haute")
    coefficient_dl: float = Field(gt=0)
    coefficient_hm: float = Field(gt=0)
    coefficient_om: float = Field(gt=0)

    def contient(self, km_annuel: float) -> bool:
        if km_annuel < self.km_min:
            return False
        return self.km_max is None or km_annuel <= self.km_max


class GrilleDryLeaseEntry(BaseModel):
    """Loyer Dry lease catalogue pour une série × tranche de durée."""

    serie_code: str
    tranche_duree: TrancheDuree
    loyer_mensuel: float = Field(gt=0, description="Loyer catalogue avant coefficient DL")


class BudgetPlanEntry(BaseModel):
    """Plancher BP HM / OM pour une série × tranche de km (section 12.3 : BP)."""

    serie_code: str
    tranche_km: TrancheKm
    bp_hm: float = Field(ge=0)
    bp_om: float = Field(ge=0)
    exercice: str = Field(description="Période de validité, ex: '2026'")


class Client(BaseModel):
    code: str
    nom: str
    rating: int = Field(ge=0, le=10)
    segment: str = ""
    cash_deposit: float = Field(default=0.0, ge=0)
    paiement_avance: bool = False


class StatutLocomotive(str, Enum):
    DISPONIBLE = "disponible"
    AFFECTEE = "affectee"
    EN_MAINTENANCE = "en_maintenance"
    HORS_SERVICE = "hors_service"


class Locomotive(BaseModel):
    numero: str
    serie_code: str
    mise_en_service: date
    km_cumules: float = Field(ge=0)
    hm_8_realisee: bool = False
    hm_16_realisee: bool = False
    statut: StatutLocomotive = StatutLocomotive.DISPONIBLE
    client_code: str | None = None

    def age_ans(self, a_date: date) -> float:
        return (a_date - self.mise_en_service).days / 365.25


class Parametres(BaseModel):
    """Paramètres globaux de tarification (section 6), tous modifiables sans
    développement via une nouvelle version du référentiel."""

    marge_hm: float = Field(default=0.15, ge=0)
    marge_om: float = Field(default=0.12, ge=0)
    marge_assurance: float = Field(default=0.05, ge=0)
    remise_maximale: float = Field(default=0.10, ge=0, le=1)
    majoration_km_supplementaire: float = Field(default=0.25, ge=0)
    seuil_remise_kam: float = Field(default=0.05, ge=0, le=1)
    bonus_vr_hm8: float = Field(default=0.04, ge=0)
    bonus_vr_hm16: float = Field(default=0.04, ge=0)
    plancher_vr_taux: float = Field(default=0.08, ge=0, le=1)
    perte_valeur_par_km_hors_reference: float = Field(default=0.20, ge=0)
    indexation_annuelle: float = Field(default=0.02, ge=0)
    validite_offre_jours: int = Field(default=30, gt=0)
    duree_max_campagne_mois: int = Field(default=3, gt=0)
    max_locos_par_contrat: int = Field(default=2, gt=0)
    seuil_rating_garantie: int = Field(default=7, ge=0, le=10)
    duree_max_rating_eleve_mois: int = Field(default=1, gt=0)
    dl_minimum: float = Field(default=10500.0, ge=0)


class Validateur(BaseModel):
    """Table Délégation (section 8.3) : un validateur par niveau de validation."""

    niveau: int = Field(ge=1, le=3, description="Niveau de validation déclenché (1 à 3)")
    nom: str
    email: str
    suppleant_email: str | None = None


class ConfigurationOffre(BaseModel):
    """Entrée du moteur de prix : une configuration à chiffrer (M3-01)."""

    client_code: str
    serie_code: str
    locomotive_numero: str | None = None
    km_annuel: float = Field(gt=0)
    duree_mois: int = Field(gt=0)
    quantite: int = Field(default=1, gt=0)
    date_debut: date
    briques_incluses: set[Brique] = Field(
        default_factory=lambda: {
            Brique.DRY_LEASE,
            Brique.HEAVY_MAINTENANCE,
            Brique.OPERATION_MAINTENANCE,
            Brique.ASSURANCE,
        }
    )
    prix_negocies: dict[Brique, float] = Field(default_factory=dict)
    age_debut_ans: float | None = Field(
        default=None,
        description="Âge de la locomotive au début du contrat si aucune locomotive n'est affectée",
    )
    km_cumules_debut: float | None = Field(
        default=None,
        description="Km cumulés au début du contrat si aucune locomotive n'est affectée",
    )
    hm_8_realisee: bool = Field(
        default=False, description="Utilisé seulement si aucune locomotive n'est affectée"
    )
    hm_16_realisee: bool = Field(
        default=False, description="Utilisé seulement si aucune locomotive n'est affectée"
    )
    campagne: bool = Field(
        default=False, description="Offre rattachée à une campagne commerciale (AMS, Renewal...)"
    )

    @model_validator(mode="after")
    def _locomotive_ou_age_km(self) -> "ConfigurationOffre":
        if self.locomotive_numero is None and (
            self.age_debut_ans is None or self.km_cumules_debut is None
        ):
            raise ValueError(
                "Sans locomotive affectée, age_debut_ans et km_cumules_debut sont requis"
            )
        return self


class EtapeCalcul(BaseModel):
    """Une ligne de l'explicabilité du prix (équivalent de l'onglet Calc, M2-04)."""

    libelle: str
    valeur: float


class StatutBrique(str, Enum):
    OK = "ok"
    ALERTE = "alerte"
    SOUS_PLANCHER = "sous_plancher"
    EXCLUE = "exclue"


class DetailBrique(BaseModel):
    brique: Brique
    cout: float = Field(ge=0)
    prix_catalogue: float = Field(ge=0)
    plancher: float = Field(ge=0)
    prix_negocie: float | None = None
    prix_retenu: float = Field(ge=0)
    statut: StatutBrique


class ResultatControle(BaseModel):
    code: str
    libelle: str
    ok: bool
    detail: str = ""


class DetailOffre(BaseModel):
    """Sortie du moteur de prix : prix détaillés, explicables, et contrôles (M2)."""

    version_referentiel: int
    par_brique: dict[Brique, DetailBrique]
    etapes_calcul: list[EtapeCalcul]

    valeur_residuelle_debut: float
    valeur_residuelle_fin: float
    perte_valeur_totale: float
    perte_valeur_mensuelle: float

    prix_km_supplementaire: float

    total_catalogue_par_loco_mensuel: float
    total_retenu_par_loco_mensuel: float
    total_plancher_par_loco_mensuel: float
    total_retenu_mensuel: float
    total_retenu_contrat: float
    remise_globale: float
    cout_reference_mensuel: float

    niveau_validation: int = Field(ge=0, le=3)
    motifs_niveau_validation: list[str]

    controles: list[ResultatControle]
    tous_controles_ok: bool
