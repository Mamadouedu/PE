"""Tests du pont Pipedrive (M3-06, part « écriture du deal »)."""

from __future__ import annotations

import pytest

from pricing_engine.offre_pdf import InMemoryOffreGenereeStore, OffreGeneree, generer_offre
from pricing_engine.pipedrive import NoOpPipedriveBridge, PipedriveResultat


class FakePipedriveBridge:
    """Pont de test : ne fait aucun appel HTTP, mémorise les deals poussés."""

    def __init__(self, deal_id_a_rendre: int | None = 42, statut: str = "pousse", erreur: str | None = None):
        self._deal_id = deal_id_a_rendre
        self._statut = statut
        self._erreur = erreur
        self.appels: list[OffreGeneree] = []

    def pousser_deal(self, offre: OffreGeneree) -> PipedriveResultat:
        self.appels.append(offre)
        if self._deal_id is None:
            return PipedriveResultat(None, None, self._statut, self._erreur)
        return PipedriveResultat(
            deal_id=self._deal_id,
            deal_url=f"https://akiem.pipedrive.com/deal/{self._deal_id}",
            statut=self._statut,
        )


def test_generer_offre_sans_pipedrive(seed_referentiel_min, configuration_offre_simple):
    """Sans bridge Pipedrive, l'offre a statut `non_configure`."""
    store = InMemoryOffreGenereeStore()
    offre, pdf = generer_offre(store, seed_referentiel_min, configuration_offre_simple, "kam@akiem.com")

    assert offre.pipedrive_statut == "non_configure"
    assert offre.pipedrive_deal_id is None
    assert offre.pipedrive_deal_url is None
    assert pdf.startswith(b"%PDF")


def test_generer_offre_avec_bridge_noop(seed_referentiel_min, configuration_offre_simple):
    """Le bridge NoOp retourne toujours `non_configure`."""
    store = InMemoryOffreGenereeStore()
    bridge = NoOpPipedriveBridge()
    offre, _ = generer_offre(
        store, seed_referentiel_min, configuration_offre_simple, "kam@akiem.com", pipedrive=bridge,
    )
    assert offre.pipedrive_statut == "non_configure"
    assert offre.pipedrive_deal_id is None


def test_generer_offre_pousse_dans_pipedrive(seed_referentiel_min, configuration_offre_simple):
    """Avec un bridge actif, l'offre reçoit un deal_id et une URL."""
    store = InMemoryOffreGenereeStore()
    bridge = FakePipedriveBridge(deal_id_a_rendre=4242)

    offre, _ = generer_offre(
        store, seed_referentiel_min, configuration_offre_simple, "kam@akiem.com", pipedrive=bridge,
    )

    assert offre.pipedrive_statut == "pousse"
    assert offre.pipedrive_deal_id == 4242
    assert offre.pipedrive_deal_url == "https://akiem.pipedrive.com/deal/4242"
    assert len(bridge.appels) == 1
    # L'offre reçue par Pipedrive doit porter son numéro définitif.
    assert bridge.appels[0].numero == offre.numero


def test_echec_pipedrive_nempeche_pas_la_generation(seed_referentiel_min, configuration_offre_simple):
    """Un échec Pipedrive est tracé mais n'empêche jamais le PDF."""
    store = InMemoryOffreGenereeStore()
    bridge = FakePipedriveBridge(deal_id_a_rendre=None, statut="echec", erreur="HTTP 500")

    offre, pdf = generer_offre(
        store, seed_referentiel_min, configuration_offre_simple, "kam@akiem.com", pipedrive=bridge,
    )

    assert pdf.startswith(b"%PDF")  # PDF toujours produit
    assert offre.pipedrive_statut == "echec"
    assert offre.pipedrive_deal_id is None
    assert offre.pipedrive_erreur == "HTTP 500"
    # Offre quand même journalisée
    assert store.lister()[0].numero == offre.numero


def test_offre_pdf_persistee_contient_deal_id(seed_referentiel_min, configuration_offre_simple):
    """Après génération, GET /offres doit renvoyer le deal_id (in-memory)."""
    store = InMemoryOffreGenereeStore()
    bridge = FakePipedriveBridge(deal_id_a_rendre=7)
    generer_offre(
        store, seed_referentiel_min, configuration_offre_simple, "kam@akiem.com", pipedrive=bridge,
    )
    rechargee = store.lister()[0]
    assert rechargee.pipedrive_deal_id == 7
    assert rechargee.pipedrive_deal_url == "https://akiem.pipedrive.com/deal/7"


@pytest.fixture
def configuration_offre_simple():
    from datetime import date
    from pricing_engine.models import ConfigurationOffre

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


@pytest.fixture
def seed_referentiel_min():
    """Référentiel minimal pour les tests Pipedrive — reprend la fixture de
    tests/conftest.py mais indépendante pour que ce fichier reste
    autonome."""
    from datetime import date
    from pricing_engine.models import (
        BudgetPlanEntry, Client, GrilleDryLeaseEntry, Locomotive, Serie,
        StatutLocomotive, TrancheDuree, TrancheKm, Validateur,
    )
    from pricing_engine.referentiel import Referentiel

    r = Referentiel()
    draft = r.nouveau_brouillon()
    serie = Serie(
        code="VECTRON", valeur_neuve=2_000_000, duree_vie_ans=30, vr_fin_vie_taux=0.10,
        km_reference_annuel=120_000, cout_hm_8_ans=150_000, cout_hm_16_ans=200_000,
        om_fixe=6_000, om_variable_eur_par_km=0.05, taux_assurance_annuel=0.03,
    )
    tranche = TrancheKm(km_min=80_000, km_max=200_000, coefficient_dl=1.0, coefficient_hm=1.0, coefficient_om=1.0)
    draft.series = {"VECTRON": serie}
    draft.tranches_km = [tranche]
    draft.grille_dry_lease = [GrilleDryLeaseEntry(
        serie_code="VECTRON", tranche_duree=TrancheDuree(duree_min_mois=0, duree_max_mois=None), loyer_mensuel=20_000,
    )]
    draft.budget_plan = [BudgetPlanEntry(serie_code="VECTRON", tranche_km=tranche, bp_hm=2_000, bp_om=1_500, exercice="2026")]
    draft.clients = {"CLIENTOK": Client(code="CLIENTOK", nom="Client", rating=5, paiement_avance=True)}
    draft.flotte = {"LOCOOK": Locomotive(
        numero="LOCOOK", serie_code="VECTRON", mise_en_service=date(2021, 1, 1),
        km_cumules=600_000, statut=StatutLocomotive.DISPONIBLE,
    )}
    draft.delegations = [Validateur(niveau=1, nom="M", email="m@a.com")]
    r.enregistrer_modification(draft, "*", "seed", None, None, "t@a.com", "test")
    r.publier(draft.numero, "t@a.com")
    return r.version_publiee()
