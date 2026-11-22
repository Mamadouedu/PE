#!/usr/bin/env python3
"""Peuple le référentiel d'une API en cours d'exécution via HTTP.

Utile quand l'API tourne en mémoire (sans DATABASE_URL) : à chaque
redémarrage d'uvicorn, le référentiel est vide et il faut le reseeder.
Contrairement à `seed_dev.py` qui écrit directement dans PostgreSQL, ce
script ne dépend que de l'API HTTP — donc marche aussi sur Windows sans
PostgreSQL.

Usage :
    uvicorn pricing_engine.api:app --reload   # dans un terminal
    python scripts/seed_http.py                # dans un autre
"""

from __future__ import annotations

import os
import sys

import httpx

BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
HEADERS = {"X-Utilisateur": "seed@akiem.com"}


def _put(client: httpx.Client, path: str, payload) -> None:
    r = client.put(f"{BASE}{path}", json=payload, headers=HEADERS)
    if r.status_code >= 400:
        print(f"PUT {path} → {r.status_code} {r.text}", file=sys.stderr)
        r.raise_for_status()


def _post(client: httpx.Client, path: str, payload=None) -> httpx.Response:
    r = client.post(f"{BASE}{path}", json=payload, headers=HEADERS)
    if r.status_code >= 400:
        print(f"POST {path} → {r.status_code} {r.text}", file=sys.stderr)
        r.raise_for_status()
    return r


def main() -> None:
    with httpx.Client(timeout=10.0) as client:
        # 1. Créer un brouillon
        r = _post(client, "/api/v1/referentiel/brouillons")
        numero = r.json()["numero"]
        print(f"Brouillon v{numero} créé")

        # 2. Série VECTRON  (body: {"serie": {...}})
        _put(client, f"/api/v1/referentiel/brouillons/{numero}/series/VECTRON", {
            "serie": {
                "code": "VECTRON",
                "valeur_neuve": 2_000_000,
                "duree_vie_ans": 30,
                "vr_fin_vie_taux": 0.10,
                "km_reference_annuel": 120_000,
                "cout_hm_8_ans": 150_000,
                "cout_hm_16_ans": 200_000,
                "om_fixe": 6_000,
                "om_variable_eur_par_km": 0.05,
                "taux_assurance_annuel": 0.03,
            }
        })

        # 3. Tranches km (body : liste)
        tranche_a = {"km_min": 80_000, "km_max": 149_999, "coefficient_dl": 1.0, "coefficient_hm": 1.0, "coefficient_om": 1.0}
        tranche_b = {"km_min": 150_000, "km_max": 200_000, "coefficient_dl": 1.05, "coefficient_hm": 1.1, "coefficient_om": 1.05}
        _put(client, f"/api/v1/referentiel/brouillons/{numero}/tranches-km", [tranche_a, tranche_b])

        # 4. Grille Dry lease (body : liste)
        _put(client, f"/api/v1/referentiel/brouillons/{numero}/grille-dry-lease", [
            {
                "serie_code": "VECTRON",
                "tranche_duree": {"duree_min_mois": 0, "duree_max_mois": None},
                "loyer_mensuel": 20_000,
            }
        ])

        # 5. Budget plan (body : liste)
        _put(client, f"/api/v1/referentiel/brouillons/{numero}/budget-plan", [
            {"serie_code": "VECTRON", "tranche_km": tranche_a, "bp_hm": 2_000, "bp_om": 1_500, "exercice": "2026"},
            {"serie_code": "VECTRON", "tranche_km": tranche_b, "bp_hm": 2_400, "bp_om": 1_800, "exercice": "2026"},
        ])

        # 6. Clients (body : objet client direct)
        for code, payload in [
            ("CLIENTOK", {"code": "CLIENTOK", "nom": "Client standard", "rating": 5, "paiement_avance": True}),
            ("CLIENTNG", {"code": "CLIENTNG", "nom": "Sans garantie", "rating": 5}),
            ("CLIENTHR", {"code": "CLIENTHR", "nom": "Rating élevé", "rating": 9, "paiement_avance": True}),
        ]:
            _put(client, f"/api/v1/referentiel/brouillons/{numero}/clients/{code}", payload)

        # 7. Flotte (1 locomotive)
        _put(client, f"/api/v1/referentiel/brouillons/{numero}/flotte/LOCOOK", {
            "numero": "LOCOOK",
            "serie_code": "VECTRON",
            "mise_en_service": "2021-01-01",
            "km_cumules": 600_000,
            "statut": "disponible",
        })

        # 8. Délégations (body : liste)
        _put(client, f"/api/v1/referentiel/brouillons/{numero}/delegations", [
            {"niveau": 1, "nom": "Manager", "email": "manager@akiem.com"},
            {"niveau": 2, "nom": "Head of Pricing", "email": "head@akiem.com"},
            {"niveau": 3, "nom": "Direction", "email": "direction@akiem.com"},
        ])

        # 9. Publier
        r = _post(client, f"/api/v1/referentiel/brouillons/{numero}/publier")
        print(f"Référentiel v{numero} publié ✓")
        print("Clients : CLIENTOK, CLIENTNG, CLIENTHR — série : VECTRON — loco : LOCOOK")
        print("\nExemple de chiffrage :")
        print(f'  POST {BASE}/api/v1/prix')
        print('  body : {"client_code":"CLIENTOK","serie_code":"VECTRON","km_annuel":120000,')
        print('          "duree_mois":24,"quantite":1,"date_debut":"2026-01-01",')
        print('          "age_debut_ans":5,"km_cumules_debut":600000}')


if __name__ == "__main__":
    main()
