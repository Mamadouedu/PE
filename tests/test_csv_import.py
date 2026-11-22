"""Tests de l'import CSV en masse."""

from __future__ import annotations

from pricing_engine.csv_import import (
    importer_budget_plan,
    importer_flotte,
    importer_grille_dry_lease,
)


def test_import_grille_dry_lease_basique():
    csv = """serie_code,duree_min_mois,duree_max_mois,loyer_mensuel
VECTRON,0,11,22000
VECTRON,12,36,20000
VECTRON,37,,18500
"""
    r = importer_grille_dry_lease(csv)
    assert r.nb_lignes_lues == 3
    assert r.nb_lignes_importees == 3
    assert r.erreurs == []
    assert len(r.grille_dry_lease) == 3
    assert r.grille_dry_lease[0].serie_code == "VECTRON"
    assert r.grille_dry_lease[0].loyer_mensuel == 22000
    # Borne haute ouverte quand duree_max_mois est vide
    assert r.grille_dry_lease[2].tranche_duree.duree_max_mois is None


def test_import_grille_dry_lease_erreur_ligne():
    csv = """serie_code,duree_min_mois,duree_max_mois,loyer_mensuel
VECTRON,0,11,20000
,0,11,15000
VECTRON,0,11,0
"""
    r = importer_grille_dry_lease(csv)
    assert r.nb_lignes_lues == 3
    assert r.nb_lignes_importees == 1  # seule la première ligne est valide
    assert len(r.erreurs) == 2
    assert "Ligne 3" in r.erreurs[0]  # serie_code manquant
    assert "Ligne 4" in r.erreurs[1]  # loyer <= 0 (violation Pydantic)


def test_import_budget_plan_deduit_les_tranches_km():
    csv = """serie_code,km_min,km_max,bp_hm,bp_om,exercice
VECTRON,80000,119999,1800,1400,2026
VECTRON,120000,139999,2000,1500,2026
VECTRON,140000,159999,2200,1600,2026
VECTRON,160000,179999,2400,1800,2026
VECTRON,180000,199999,2600,2000,2026
VECTRON,200000,220000,2800,2200,2026
TRAXX,80000,119999,1600,1200,2026
"""
    r = importer_budget_plan(csv)
    assert r.nb_lignes_lues == 7
    assert r.nb_lignes_importees == 7
    assert r.erreurs == []
    # Les tranches km sont dédupliquées : 6 tranches distinctes
    assert len(r.tranches_km) == 6
    # Triées par km_min croissant
    assert r.tranches_km[0].km_min == 80000
    assert r.tranches_km[-1].km_min == 200000


def test_import_budget_plan_erreur_km_manquant():
    csv = """serie_code,km_min,km_max,bp_hm,bp_om,exercice
VECTRON,,119999,1800,1400,2026
"""
    r = importer_budget_plan(csv)
    assert r.nb_lignes_lues == 1
    assert r.nb_lignes_importees == 0
    assert len(r.erreurs) == 1
    assert "km_min" in r.erreurs[0]


def test_import_flotte_avec_produit_sous_serie_homologations():
    csv = """numero,produit,sous_serie,serie_code,homologations,mise_en_service,km_cumules,statut
BR186-001,TRAXX,DC2,VECTRON,PL;DE,2021-01-01,600000,disponible
BR186-002,TRAXX,DC3,VECTRON,PL;DE;AT;CZ,2022-06-15,450000,disponible
193-901,VECTRON,MS,VECTRON,DE;AT;CZ;SK;HU;PL,2020-03-01,800000,en_maintenance
"""
    r = importer_flotte(csv)
    assert r.nb_lignes_lues == 3
    assert r.nb_lignes_importees == 3
    assert r.erreurs == []
    assert len(r.locomotives) == 3
    loco1 = r.locomotives[0]
    assert loco1.produit == "TRAXX"
    assert loco1.sous_serie == "DC2"
    assert loco1.homologations == ["PL", "DE"]
    assert loco1.homologuee_dans("pl")  # case-insensitive
    loco3 = r.locomotives[2]
    assert len(loco3.homologations) == 6  # DE;AT;CZ;SK;HU;PL


def test_import_flotte_statut_inconnu_remonte_une_erreur():
    csv = """numero,produit,sous_serie,serie_code,homologations,mise_en_service,km_cumules,statut
BR186-001,TRAXX,DC2,VECTRON,PL,2021-01-01,600000,RETIREE
"""
    r = importer_flotte(csv)
    assert r.nb_lignes_lues == 1
    assert r.nb_lignes_importees == 0
    assert any("statut inconnu" in e for e in r.erreurs)


def test_import_flotte_avec_bom_utf8():
    """Excel sauve souvent les CSV avec un BOM UTF-8 au début — on doit le
    manger silencieusement, sinon la 1re colonne est 'nommée' avec le BOM."""
    csv = "﻿" + "numero,produit,sous_serie,serie_code,homologations,mise_en_service,km_cumules,statut\n"
    csv += "LOCO1,TRAXX,DC2,VECTRON,PL,2021-01-01,600000,disponible\n"
    r = importer_flotte(csv)
    assert r.nb_lignes_importees == 1
    assert r.locomotives[0].numero == "LOCO1"


def test_virgule_decimale_acceptee():
    """Pour les utilisateurs francophones, `150000,5` doit marcher comme `150000.5`."""
    csv = """serie_code,km_min,km_max,bp_hm,bp_om,exercice
VECTRON,80000,119999,"1800,5","1400,25",2026
"""
    r = importer_budget_plan(csv)
    assert r.nb_lignes_importees == 1
    assert r.budget_plan[0].bp_hm == 1800.5
    assert r.budget_plan[0].bp_om == 1400.25
