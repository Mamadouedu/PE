#!/usr/bin/env python3
"""Peuple une base PostgreSQL avec les mêmes données que les tests
(`tests/conftest.py`), pour pouvoir utiliser le configurateur KAM en local
sans ressaisir un référentiel à la main.

Usage :
    DATABASE_URL=postgresql+psycopg://pricing:pricing@localhost/pricing_dev \
        python3 scripts/seed_dev.py
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pricing_engine.db import SqlAlchemyReferentielBackend, make_session_factory  # noqa: E402
from pricing_engine.models import (  # noqa: E402
    BudgetPlanEntry,
    Client,
    GrilleDryLeaseEntry,
    Locomotive,
    Serie,
    StatutLocomotive,
    TrancheDuree,
    TrancheKm,
    Validateur,
)
from pricing_engine.referentiel import Referentiel  # noqa: E402

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://pricing:pricing@localhost/pricing_dev"
)


def main() -> None:
    backend = SqlAlchemyReferentielBackend(make_session_factory(DATABASE_URL))
    referentiel = Referentiel(backend)

    draft = referentiel.nouveau_brouillon()

    serie_vectron = Serie(
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
    tranche_a = TrancheKm(
        km_min=80_000, km_max=149_999, coefficient_dl=1.0, coefficient_hm=1.0, coefficient_om=1.0
    )
    tranche_b = TrancheKm(
        km_min=150_000, km_max=200_000, coefficient_dl=1.05, coefficient_hm=1.1, coefficient_om=1.05
    )

    draft.series = {"VECTRON": serie_vectron}
    draft.tranches_km = [tranche_a, tranche_b]
    draft.grille_dry_lease = [
        GrilleDryLeaseEntry(
            serie_code="VECTRON",
            tranche_duree=TrancheDuree(duree_min_mois=0, duree_max_mois=None),
            loyer_mensuel=20_000,
        )
    ]
    draft.budget_plan = [
        BudgetPlanEntry(
            serie_code="VECTRON", tranche_km=tranche_a, bp_hm=2_000, bp_om=1_500, exercice="2026"
        ),
        BudgetPlanEntry(
            serie_code="VECTRON", tranche_km=tranche_b, bp_hm=2_400, bp_om=1_800, exercice="2026"
        ),
    ]
    draft.clients = {
        "CLIENTOK": Client(code="CLIENTOK", nom="Client standard", rating=5, paiement_avance=True),
        "CLIENTNG": Client(code="CLIENTNG", nom="Sans garantie", rating=5),
        "CLIENTHR": Client(code="CLIENTHR", nom="Rating élevé", rating=9, paiement_avance=True),
    }
    draft.flotte = {
        "LOCOOK": Locomotive(
            numero="LOCOOK",
            serie_code="VECTRON",
            mise_en_service=date(2021, 1, 1),
            km_cumules=600_000,
            statut=StatutLocomotive.DISPONIBLE,
        ),
    }
    draft.delegations = [
        Validateur(niveau=1, nom="Manager", email="manager@akiem.com"),
        Validateur(niveau=2, nom="Head of Pricing", email="head@akiem.com"),
        Validateur(niveau=3, nom="Direction", email="direction@akiem.com"),
    ]

    referentiel.enregistrer_modification(
        draft,
        table="*",
        action="seed",
        avant=None,
        apres=None,
        utilisateur="seed@akiem.com",
        raison="Données de démonstration (scripts/seed_dev.py)",
    )

    anomalies = referentiel.publier(draft.numero, "seed@akiem.com")
    bloquantes = [a for a in anomalies if a.bloquante]
    if bloquantes:
        print("Publication bloquée :")
        for a in bloquantes:
            print(f"  - {a.code} : {a.message}")
        raise SystemExit(1)

    print(f"Référentiel v{draft.numero} publié sur {DATABASE_URL}")
    print("Clients : CLIENTOK, CLIENTNG, CLIENTHR — série : VECTRON — loco : LOCOOK")


if __name__ == "__main__":
    main()
