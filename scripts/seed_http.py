#!/usr/bin/env python3
"""Peuple le référentiel d'une API en cours d'exécution via HTTP.

Utile quand l'API tourne en mémoire (sans DATABASE_URL) : à chaque
redémarrage d'uvicorn, le référentiel est vide et il faut le reseeder.
Contrairement à `seed_dev.py` qui écrit directement dans PostgreSQL, ce
script ne dépend que de l'API HTTP — donc marche aussi sur Windows sans
PostgreSQL.

Jeu de données :
- 3 séries (VECTRON, TRAXX, EURODUAL)
- 6 tranches de km (80-120, 120-140, 140-160, 160-180, 180-200, 200-220)
  importées via CSV budget_plan
- grille Dry lease par CSV (3 séries × 3 tranches de durée)
- 10 locomotives réalistes (produit, sous-série, homologations)
- 3 clients, 3 validateurs

Usage :
    uvicorn pricing_engine.api:app --reload   # dans un terminal
    python scripts/seed_http.py                # dans un autre
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
HEADERS = {"X-Utilisateur": "seed@akiem.com"}
CSV_DIR = Path(__file__).parent / "csv_exemples"


def _put(client: httpx.Client, path: str, payload) -> None:
    r = client.put(f"{BASE}{path}", json=payload, headers=HEADERS)
    if r.status_code >= 400:
        print(f"PUT {path} → {r.status_code} {r.text[:200]}", file=sys.stderr)
        r.raise_for_status()


def _post(client: httpx.Client, path: str, payload=None) -> httpx.Response:
    r = client.post(f"{BASE}{path}", json=payload, headers=HEADERS)
    if r.status_code >= 400:
        print(f"POST {path} → {r.status_code} {r.text[:200]}", file=sys.stderr)
        r.raise_for_status()
    return r


def _post_csv(client: httpx.Client, path: str, csv_path: Path) -> dict:
    with open(csv_path, "rb") as f:
        files = {"fichier": (csv_path.name, f, "text/csv")}
        r = client.post(f"{BASE}{path}", files=files, headers=HEADERS)
    if r.status_code >= 400:
        print(f"POST {path} → {r.status_code} {r.text[:200]}", file=sys.stderr)
        r.raise_for_status()
    return r.json()


def main() -> None:
    with httpx.Client(timeout=30.0) as client:
        r = _post(client, "/api/v1/referentiel/brouillons")
        numero = r.json()["numero"]
        print(f"Brouillon v{numero} créé")

        # Les 3 séries (produits)
        series_payload = {
            "VECTRON": {
                "code": "VECTRON", "valeur_neuve": 3_200_000, "duree_vie_ans": 30,
                "vr_fin_vie_taux": 0.10, "km_reference_annuel": 150_000,
                "cout_hm_8_ans": 150_000, "cout_hm_16_ans": 200_000,
                "om_fixe": 6_000, "om_variable_eur_par_km": 0.05, "taux_assurance_annuel": 0.03,
            },
            "TRAXX": {
                "code": "TRAXX", "valeur_neuve": 2_800_000, "duree_vie_ans": 30,
                "vr_fin_vie_taux": 0.10, "km_reference_annuel": 140_000,
                "cout_hm_8_ans": 140_000, "cout_hm_16_ans": 190_000,
                "om_fixe": 5_500, "om_variable_eur_par_km": 0.045, "taux_assurance_annuel": 0.03,
            },
            "EURODUAL": {
                "code": "EURODUAL", "valeur_neuve": 3_800_000, "duree_vie_ans": 30,
                "vr_fin_vie_taux": 0.10, "km_reference_annuel": 130_000,
                "cout_hm_8_ans": 170_000, "cout_hm_16_ans": 220_000,
                "om_fixe": 7_000, "om_variable_eur_par_km": 0.06, "taux_assurance_annuel": 0.035,
            },
        }
        for code, payload in series_payload.items():
            _put(client, f"/api/v1/referentiel/brouillons/{numero}/series/{code}", {"serie": payload})

        # Budget plan + tranches km (via CSV)
        res_bp = _post_csv(client, f"/api/v1/referentiel/brouillons/{numero}/import/budget-plan", CSV_DIR / "budget_plan.csv")
        print(f"BP importé : {res_bp['nb_lignes_importees']} lignes, {res_bp['nb_tranches_km_deduites']} tranches km déduites")

        # Grille Dry lease (via CSV)
        res_dl = _post_csv(client, f"/api/v1/referentiel/brouillons/{numero}/import/dry-lease-grille", CSV_DIR / "grille_dry_lease.csv")
        print(f"Grille DL importée : {res_dl['nb_lignes_importees']} lignes")

        # Clients
        for code, payload in [
            ("CLIENTOK", {"code": "CLIENTOK", "nom": "Client standard", "rating": 5, "paiement_avance": True}),
            ("CLIENTNG", {"code": "CLIENTNG", "nom": "Sans garantie", "rating": 5}),
            ("CLIENTHR", {"code": "CLIENTHR", "nom": "Rating élevé", "rating": 9, "paiement_avance": True}),
        ]:
            _put(client, f"/api/v1/referentiel/brouillons/{numero}/clients/{code}", payload)

        # Flotte (via CSV)
        res_fl = _post_csv(client, f"/api/v1/referentiel/brouillons/{numero}/import/flotte?remplacer=true", CSV_DIR / "flotte.csv")
        print(f"Flotte importée : {res_fl['nb_lignes_importees']} locomotives")

        # Délégations
        _put(client, f"/api/v1/referentiel/brouillons/{numero}/delegations", [
            {"niveau": 1, "nom": "Manager", "email": "manager@akiem.com"},
            {"niveau": 2, "nom": "Head of Pricing", "email": "head@akiem.com"},
            {"niveau": 3, "nom": "Direction", "email": "direction@akiem.com"},
        ])

        # Publier
        _post(client, f"/api/v1/referentiel/brouillons/{numero}/publier")
        print(f"\nRéférentiel v{numero} publié ✓")
        print(f"  Séries : {', '.join(series_payload.keys())}")
        print(f"  Clients : CLIENTOK, CLIENTNG, CLIENTHR")
        print(f"  Flotte : 10 locos (TRAXX DC2/DC3/MS2, VECTRON MS/AC, EURODUAL BiMode)")
        print(f"\nExemple de chiffrage :")
        print(f'  POST {BASE}/api/v1/prix')
        print('  body : {"client_code":"CLIENTOK","serie_code":"VECTRON","km_annuel":150000,')
        print('          "duree_mois":24,"quantite":1,"date_debut":"2026-01-01",')
        print('          "age_debut_ans":5,"km_cumules_debut":600000}')


if __name__ == "__main__":
    main()
