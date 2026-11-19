"""Operation maintenance — section 6.1 :

coût mensuel = (OM fixe + OM €/km × km annuel ÷ 12) × coefficient OM
prix catalogue = max(coût × (1 + marge OM), BP OM) ; plancher = BP OM
"""

from datetime import date

import pytest

from pricing_engine.engine import calculer_offre
from pricing_engine.models import (
    Brique,
    BudgetPlanEntry,
    Client,
    ConfigurationOffre,
    GrilleDryLeaseEntry,
    Parametres,
    Serie,
    TrancheDuree,
    TrancheKm,
)
from pricing_engine.referentiel import StatutVersion, VersionReferentiel


def test_bp_om_bloque_le_prix_catalogue(version_publiee, config_base):
    offre = calculer_offre(version_publiee, config_base)
    om = offre.par_brique[Brique.OPERATION_MAINTENANCE]

    cout_mensuel = (6_000 + 0.05 * 120_000) / 12 * 1.0
    assert cout_mensuel == pytest.approx(1_000.0)
    assert cout_mensuel * 1.12 < 1_500.0  # le BP OM (1 500) domine
    assert om.cout == pytest.approx(cout_mensuel)
    assert om.prix_catalogue == pytest.approx(1_500.0)
    assert om.plancher == pytest.approx(1_500.0)


def test_cout_plus_marge_domine_quand_superieur_au_bp():
    """Isolé du cas BP-dominant par défaut : un OM/km élevé fait gagner le coût + marge."""

    serie = Serie(
        code="S1",
        valeur_neuve=1_000_000,
        km_reference_annuel=120_000,
        cout_hm_8_ans=0,
        cout_hm_16_ans=0,
        om_fixe=0,
        om_variable_eur_par_km=0.50,  # très élevé pour ce test
        taux_assurance_annuel=0.0,
    )
    tranche = TrancheKm(km_min=0, km_max=None, coefficient_dl=1.0, coefficient_hm=1.0, coefficient_om=1.0)
    version = VersionReferentiel(numero=1, statut=StatutVersion.PUBLIE)
    version.series["S1"] = serie
    version.tranches_km = [tranche]
    version.grille_dry_lease = [
        GrilleDryLeaseEntry(
            serie_code="S1",
            tranche_duree=TrancheDuree(duree_min_mois=0, duree_max_mois=None),
            loyer_mensuel=1_000,
        )
    ]
    version.budget_plan = [
        BudgetPlanEntry(serie_code="S1", tranche_km=tranche, bp_hm=0, bp_om=100, exercice="2026")
    ]
    version.clients["C1"] = Client(code="C1", nom="Client", rating=1, paiement_avance=True)
    version.parametres = Parametres()

    config = ConfigurationOffre(
        client_code="C1",
        serie_code="S1",
        km_annuel=120_000,
        duree_mois=12,
        date_debut=date(2026, 1, 1),
        age_debut_ans=1,
        km_cumules_debut=120_000,
    )
    offre = calculer_offre(version, config)
    om = offre.par_brique[Brique.OPERATION_MAINTENANCE]

    cout_mensuel = (0 + 0.50 * 120_000) / 12 * 1.0
    assert cout_mensuel == pytest.approx(5_000.0)
    attendu_catalogue = cout_mensuel * 1.12
    assert attendu_catalogue > 100.0  # le BP OM (plancher) ne domine plus
    assert om.prix_catalogue == pytest.approx(attendu_catalogue)
    assert om.plancher == pytest.approx(100.0)
