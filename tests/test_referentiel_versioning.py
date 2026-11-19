"""Référentiel versionné — M1-02 à M1-05."""

from datetime import date

from pricing_engine.models import Locomotive, Serie, StatutLocomotive, TrancheKm
from pricing_engine.referentiel import Referentiel, StatutVersion


def _serie_minimale(code: str = "S1") -> Serie:
    return Serie(
        code=code,
        valeur_neuve=1_000_000,
        km_reference_annuel=120_000,
        cout_hm_8_ans=100_000,
        cout_hm_16_ans=100_000,
        om_fixe=1_000,
        om_variable_eur_par_km=0.05,
        taux_assurance_annuel=0.03,
    )


def test_publication_bloquee_par_anomalie_bloquante():
    referentiel = Referentiel()
    draft = referentiel.nouveau_brouillon()
    draft.series["S1"] = _serie_minimale()
    # Locomotive référençant une série inconnue -> anomalie bloquante (M1-04).
    draft.flotte["L1"] = Locomotive(
        numero="L1", serie_code="INCONNUE", mise_en_service=date(2020, 1, 1), km_cumules=0
    )

    anomalies = referentiel.publier(draft.numero, "pricing@akiem.com")

    assert any(a.bloquante for a in anomalies)
    assert referentiel.version(draft.numero).statut == StatutVersion.BROUILLON
    assert referentiel.version_publiee() is None


def test_publication_reussie_archive_l_ancienne_version():
    referentiel = Referentiel()

    draft1 = referentiel.nouveau_brouillon()
    draft1.series["S1"] = _serie_minimale()
    anomalies1 = referentiel.publier(draft1.numero, "pricing@akiem.com")
    assert not any(a.bloquante for a in anomalies1)
    assert referentiel.version_publiee().numero == draft1.numero

    draft2 = referentiel.nouveau_brouillon()
    assert draft2.series["S1"].code == "S1"  # copié depuis la version publiée
    draft2.series["S2"] = _serie_minimale("S2")
    anomalies2 = referentiel.publier(draft2.numero, "pricing@akiem.com")

    assert not any(a.bloquante for a in anomalies2)
    assert referentiel.version_publiee().numero == draft2.numero
    assert referentiel.version(draft1.numero).statut == StatutVersion.ARCHIVE


def test_journal_enregistre_qui_quand_avant_apres_raison():
    referentiel = Referentiel()
    draft = referentiel.nouveau_brouillon()

    referentiel.enregistrer_modification(
        draft=draft,
        table="series",
        action="set",
        avant=None,
        apres=_serie_minimale(),
        utilisateur="kam@akiem.com",
        raison="Création de la série",
    )

    entree = referentiel.journal[-1]
    assert entree.utilisateur == "kam@akiem.com"
    assert entree.table == "series"
    assert entree.raison == "Création de la série"
    assert entree.avant is None


def test_controle_qualite_detecte_les_bornes_non_croissantes():
    referentiel = Referentiel()
    draft = referentiel.nouveau_brouillon()
    draft.tranches_km = [
        TrancheKm(km_min=100_000, km_max=50_000, coefficient_dl=1, coefficient_hm=1, coefficient_om=1)
    ]

    anomalies = referentiel.controler_qualite(draft)
    assert any(a.code == "TRANCHE_KM_BORNES_NON_CROISSANTES" for a in anomalies)


def test_controle_qualite_signale_bp_et_grille_manquants_sans_bloquer():
    referentiel = Referentiel()
    draft = referentiel.nouveau_brouillon()
    draft.series["S1"] = _serie_minimale()

    anomalies = referentiel.controler_qualite(draft)
    codes = {a.code for a in anomalies}
    assert "GRILLE_MANQUANTE" in codes
    assert "BP_MANQUANT" in codes
    assert not any(a.bloquante for a in anomalies if a.code in {"GRILLE_MANQUANTE", "BP_MANQUANT"})
