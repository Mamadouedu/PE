#!/usr/bin/env python3
"""CLI d'import de la flotte Akiem depuis un CSV.

Usage :
    # Dry-run : valide le CSV, rapporte, n'écrit rien
    python scripts/import_fleet_csv.py flotte_akiem.csv

    # Apply : écrit en base après validation
    python scripts/import_fleet_csv.py flotte_akiem.csv --apply

    # URL de base explicite (sinon CATALOG_DATABASE_URL de l'env, ou
    # in-memory si aucune des deux)
    python scripts/import_fleet_csv.py flotte_akiem.csv --apply \\
        --database-url postgresql+psycopg://pricing:pricing@localhost/pricing

Format CSV attendu :
    asset_number,vehicle_registration_number,technical_variant_code,
    manufacturing_year,commissioning_date,ownership_status,
    operational_status,current_mileage_km,current_engine_hours,
    current_country_iso,current_ecm_provider_code,notes

Exit codes :
    0 : import OK (dry-run réussi, ou apply commité)
    1 : erreurs de validation (lignes rejetées)
    2 : erreurs d'invocation (fichier introuvable, URL invalide, etc.)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ajoute src/ au sys.path pour pouvoir exécuter le script sans install
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from pricing_engine.catalog.csv_fleet_import import import_fleet_csv  # noqa: E402
from pricing_engine.catalog.seed import seed_catalog_akiem             # noqa: E402
from pricing_engine.catalog.seed_lot2 import seed_lot2                 # noqa: E402
from pricing_engine.catalog.seed_lot3 import seed_lot3                 # noqa: E402
from pricing_engine.catalog.seed_lot5 import seed_lot5                 # noqa: E402
from pricing_engine.catalog.store import InMemoryCatalogStore          # noqa: E402


def _build_store(database_url: str | None):
    """Construit un store SQL si une URL est fournie, sinon in-memory
    seedé (pratique pour tester un CSV sans PG)."""
    if database_url:
        from pricing_engine.catalog.db import create_all_catalog_tables
        from pricing_engine.catalog.sql_store import (
            SqlAlchemyCatalogStore,
            make_catalog_session_factory,
        )
        from sqlalchemy import create_engine
        engine = create_engine(database_url, future=True)
        # Assure que les tables existent (en prod on passe par Alembic,
        # mais en dev/import ad-hoc ce fallback est pratique)
        create_all_catalog_tables(engine)
        sf = make_catalog_session_factory(database_url)
        store = SqlAlchemyCatalogStore(sf)
        if not store.list_manufacturers():
            seed_catalog_akiem(store)
            seed_lot2(store)
            seed_lot3(store)
            seed_lot5(store)
        return store

    store = InMemoryCatalogStore()
    seed_catalog_akiem(store)
    seed_lot2(store)
    seed_lot3(store)
    seed_lot5(store)
    return store


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("csv_file", type=Path, help="Fichier CSV à importer")
    p.add_argument("--apply", action="store_true",
                   help="Applique l'import en base (par défaut : dry-run)")
    p.add_argument("--database-url", default=os.environ.get("CATALOG_DATABASE_URL"),
                   help="URL SQLAlchemy de la base catalog "
                        "(défaut : CATALOG_DATABASE_URL ou in-memory)")
    args = p.parse_args()

    if not args.csv_file.exists():
        print(f"Erreur: fichier introuvable: {args.csv_file}", file=sys.stderr)
        return 2

    contents = args.csv_file.read_text(encoding="utf-8")
    store = _build_store(args.database_url)
    result = import_fleet_csv(contents, store, dry_run=not args.apply)
    print(result.summary())

    if result.rejected_rows > 0:
        return 1
    if args.apply and not result.applied:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
