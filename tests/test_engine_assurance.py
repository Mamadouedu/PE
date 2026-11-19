"""Assurance — section 6.1 :

prime = valeur résiduelle moyenne du contrat × taux annuel de la série ÷ 12
prix catalogue = prime × (1 + marge assurance) ; plancher = prime
"""

import pytest

from pricing_engine.engine import calculer_offre
from pricing_engine.models import Brique


def test_prime_et_prix_catalogue_assurance(version_publiee, config_base):
    offre = calculer_offre(version_publiee, config_base)
    assurance = offre.par_brique[Brique.ASSURANCE]

    vr_moyenne = (offre.valeur_residuelle_debut + offre.valeur_residuelle_fin) / 2
    prime_attendue = vr_moyenne * 0.03 / 12

    assert assurance.cout == pytest.approx(prime_attendue)
    assert assurance.plancher == pytest.approx(prime_attendue)
    assert assurance.prix_catalogue == pytest.approx(prime_attendue * 1.05)
    assert assurance.prix_retenu == pytest.approx(prime_attendue * 1.05)


def test_prime_suit_la_valeur_residuelle_moyenne(version_publiee, config_base):
    offre_courte = calculer_offre(version_publiee, config_base.model_copy(update={"duree_mois": 12}))
    offre_longue = calculer_offre(version_publiee, config_base.model_copy(update={"duree_mois": 60}))

    # Plus la durée est longue, plus la loco vieillit/s'use : la VR moyenne
    # baisse, donc la prime (coût) baisse aussi.
    assurance_courte = offre_courte.par_brique[Brique.ASSURANCE]
    assurance_longue = offre_longue.par_brique[Brique.ASSURANCE]
    assert assurance_longue.cout < assurance_courte.cout
