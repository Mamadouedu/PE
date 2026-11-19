from datetime import date

import pytest

from pricing_engine.models import (
    BudgetPlanEntry,
    Client,
    ConfigurationOffre,
    GrilleDryLeaseEntry,
    Locomotive,
    Parametres,
    Serie,
    StatutLocomotive,
    TrancheDuree,
    TrancheKm,
    Validateur,
)
from pricing_engine.referentiel import StatutVersion, VersionReferentiel

SERIE_VECTRON = Serie(
    code="VECTRON",
    valeur_neuve=2_000_000,
    duree_vie_ans=30,
    vr_fin_vie_taux=0.10,
    km_reference_annuel=120_000,
    cout_hm_8_ans=150_000,
    cout_hm_16_ans=200_000,
    om_fixe=6_000,
    om_variable_eur_par_km=0.05,
    taux_assurance_annuel=0.03,
)

TRANCHE_KM_A = TrancheKm(
    km_min=80_000, km_max=149_999, coefficient_dl=1.0, coefficient_hm=1.0, coefficient_om=1.0
)
TRANCHE_KM_B = TrancheKm(
    km_min=150_000, km_max=200_000, coefficient_dl=1.05, coefficient_hm=1.1, coefficient_om=1.05
)

GRILLE_VECTRON = GrilleDryLeaseEntry(
    serie_code="VECTRON",
    tranche_duree=TrancheDuree(duree_min_mois=0, duree_max_mois=None),
    loyer_mensuel=20_000,
)

BP_VECTRON_A = BudgetPlanEntry(
    serie_code="VECTRON", tranche_km=TRANCHE_KM_A, bp_hm=2_000, bp_om=1_500, exercice="2026"
)
BP_VECTRON_B = BudgetPlanEntry(
    serie_code="VECTRON", tranche_km=TRANCHE_KM_B, bp_hm=2_400, bp_om=1_800, exercice="2026"
)

CLIENT_OK = Client(code="CLIENTOK", nom="Client standard", rating=5, paiement_avance=True)
CLIENT_SANS_GARANTIE = Client(code="CLIENTNG", nom="Sans garantie", rating=5)
CLIENT_RATING_ELEVE = Client(code="CLIENTHR", nom="Rating élevé", rating=9, paiement_avance=True)

LOCO_OK = Locomotive(
    numero="LOCOOK",
    serie_code="VECTRON",
    mise_en_service=date(2021, 1, 1),
    km_cumules=600_000,
    statut=StatutLocomotive.DISPONIBLE,
)
LOCO_KO = Locomotive(
    numero="LOCOKO",
    serie_code="VECTRON",
    mise_en_service=date(2021, 1, 1),
    km_cumules=600_000,
    statut=StatutLocomotive.EN_MAINTENANCE,
)
LOCO_AUTRE_SERIE = Locomotive(
    numero="LOCOAS",
    serie_code="TRAXX",
    mise_en_service=date(2021, 1, 1),
    km_cumules=600_000,
    statut=StatutLocomotive.DISPONIBLE,
)


@pytest.fixture
def version_publiee() -> VersionReferentiel:
    version = VersionReferentiel(numero=1, statut=StatutVersion.PUBLIE)
    version.series[SERIE_VECTRON.code] = SERIE_VECTRON
    version.tranches_km = [TRANCHE_KM_A, TRANCHE_KM_B]
    version.grille_dry_lease = [GRILLE_VECTRON]
    version.budget_plan = [BP_VECTRON_A, BP_VECTRON_B]
    version.clients = {
        CLIENT_OK.code: CLIENT_OK,
        CLIENT_SANS_GARANTIE.code: CLIENT_SANS_GARANTIE,
        CLIENT_RATING_ELEVE.code: CLIENT_RATING_ELEVE,
    }
    version.flotte = {
        LOCO_OK.numero: LOCO_OK,
        LOCO_KO.numero: LOCO_KO,
        LOCO_AUTRE_SERIE.numero: LOCO_AUTRE_SERIE,
    }
    version.parametres = Parametres()
    version.delegations = [
        Validateur(niveau=1, nom="Manager", email="manager@akiem.com"),
        Validateur(niveau=2, nom="Head of Pricing", email="head@akiem.com"),
        Validateur(niveau=3, nom="Direction", email="direction@akiem.com"),
    ]
    return version


@pytest.fixture
def config_base() -> ConfigurationOffre:
    return ConfigurationOffre(
        client_code="CLIENTOK",
        serie_code="VECTRON",
        km_annuel=120_000,
        duree_mois=24,
        quantite=1,
        date_debut=date(2026, 1, 1),
        age_debut_ans=5,
        km_cumules_debut=600_000,
    )
