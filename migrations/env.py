"""Alembic environment Akiem Pricing.

Lit `DATABASE_URL` depuis l'environnement si fourni, sinon utilise la
valeur dans alembic.ini. Branche target_metadata sur les métadonnées
SQLAlchemy du projet pour permettre `alembic revision --autogenerate`.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Ajoute src/ au PYTHONPATH pour importer pricing_engine depuis la racine
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Métadonnées existantes (Lot 1 original) + nouvelles (catalog SQL)
from pricing_engine.db import Base as LegacyBase  # noqa: E402
from pricing_engine.catalog.db import Base as CatalogBase  # noqa: E402


# Fusionner les deux metadata en une seule pour Alembic
from sqlalchemy import MetaData
combined_metadata = MetaData()
for tbl in LegacyBase.metadata.tables.values():
    tbl.tometadata(combined_metadata)
for tbl in CatalogBase.metadata.tables.values():
    tbl.tometadata(combined_metadata)
target_metadata = combined_metadata


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url depuis DATABASE_URL (12-factor)
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
