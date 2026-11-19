"""Offre PDF — numérotation, journalisation, contenu filtré (M3-05)."""

import io

import pytest
from pypdf import PdfReader

from pricing_engine.models import Brique
from pricing_engine.offre_pdf import InMemoryOffreGenereeStore, formater_numero, generer_offre


def _texte_pdf(pdf_bytes: bytes) -> str:
    """Le flux PDF est encodé (ASCII85/Flate) : chercher une sous-chaîne
    dans les octets bruts ne prouve rien. On extrait le texte réellement
    rendu, comme le ferait un lecteur PDF."""

    lecteur = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() for page in lecteur.pages)


def test_numerotation_sequentielle(version_publiee, config_base):
    store = InMemoryOffreGenereeStore()

    offre1, _ = generer_offre(store, version_publiee, config_base, "kam@akiem.com")
    offre2, _ = generer_offre(store, version_publiee, config_base, "kam@akiem.com")

    assert offre1.numero == "AK-000001"
    assert offre2.numero == "AK-000002"
    assert formater_numero(42) == "AK-000042"


def test_offre_generee_est_journalisee(version_publiee, config_base):
    store = InMemoryOffreGenereeStore()

    offre, _ = generer_offre(store, version_publiee, config_base, "kam@akiem.com")

    journal = store.lister()
    assert len(journal) == 1
    assert journal[0].numero == offre.numero
    assert journal[0].utilisateur == "kam@akiem.com"
    assert journal[0].client_code == "CLIENTOK"
    assert journal[0].niveau_validation == 0


def test_le_pdf_commence_par_l_entete_pdf(version_publiee, config_base):
    store = InMemoryOffreGenereeStore()

    _, pdf_bytes = generer_offre(store, version_publiee, config_base, "kam@akiem.com")

    assert pdf_bytes[:5] == b"%PDF-"


def test_le_pdf_ne_contient_jamais_de_cout_ni_de_marge(version_publiee, config_base):
    """Même sans plancher/catalogue dans le PDF (voir l'en-tête du module),
    on vérifie ici que les vrais chiffres de coût (différents des prix) ne
    s'y trouvent pas non plus, comme filet de sécurité."""

    store = InMemoryOffreGenereeStore()

    offre_calculee, pdf_bytes = generer_offre(store, version_publiee, config_base, "kam@akiem.com")
    texte = _texte_pdf(pdf_bytes).lower()

    # Le plancher BP de l'OM (1500) et le catalogue HM ne doivent pas
    # apparaître : seul le prix retenu doit être imprimé.
    assert "plancher" not in texte
    assert "catalogue" not in texte
    assert "marge" not in texte


def test_mention_projet_presente_si_niveau_superieur_a_zero(version_publiee, config_base):
    store = InMemoryOffreGenereeStore()
    config = config_base.model_copy(update={"prix_negocies": {Brique.OPERATION_MAINTENANCE: 1_400.0}})

    offre, pdf_bytes = generer_offre(store, version_publiee, config, "kam@akiem.com")

    assert offre.niveau_validation == 2
    assert "PROJET" in _texte_pdf(pdf_bytes)


def test_mention_projet_absente_si_dans_les_regles(version_publiee, config_base):
    store = InMemoryOffreGenereeStore()

    offre, pdf_bytes = generer_offre(store, version_publiee, config_base, "kam@akiem.com")

    assert offre.niveau_validation == 0
    assert "PROJET" not in _texte_pdf(pdf_bytes)


def test_le_pdf_affiche_le_numero_le_client_et_les_prix_retenus(version_publiee, config_base):
    store = InMemoryOffreGenereeStore()

    offre, pdf_bytes = generer_offre(store, version_publiee, config_base, "kam@akiem.com")
    texte = _texte_pdf(pdf_bytes)

    assert offre.numero in texte
    assert "Client standard" in texte  # nom du client (CLIENTOK), pas son code
    assert "20" in texte and "000.00" in texte  # Dry lease retenu = 20 000,00 €


def test_erreur_de_calcul_se_propage(version_publiee, config_base):
    store = InMemoryOffreGenereeStore()
    config = config_base.model_copy(update={"serie_code": "INCONNUE"})

    with pytest.raises(KeyError):
        generer_offre(store, version_publiee, config, "kam@akiem.com")
