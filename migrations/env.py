"""Alembic env.py — wires Alembic to the project's ORM models.

Two non-default choices live here:

  1. `target_metadata = Base.metadata` from the project's orm_models.
     This is what makes `alembic revision --autogenerate` see every
     ORM table and produce a real migration. Without it autogenerate
     produces an empty file.

  2. The database URL is read from `SUPPORT_AUTOMATION_DATABASE_URL`
     at runtime, not from alembic.ini. The same env var the rest of
     the app uses — so `alembic upgrade head` always targets the same
     database the cron jobs and the API are talking to.

The script_location stays as the default `migrations/`.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make the project root importable so `adapters.persistence.orm_models`
# resolves when alembic is run from the project directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from adapters.persistence.orm_models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# `--autogenerate` reads this to know which tables should exist.
target_metadata = Base.metadata


def _resolve_url() -> str:
    """Pull the URL from the env var the rest of the app uses.

    Falls back to whatever's in alembic.ini only when the env var is
    absent — useful when running `alembic --help` or other commands
    that don't need a real connection.
    """
    env_url = os.environ.get("SUPPORT_AUTOMATION_DATABASE_URL")
    if env_url:
        return env_url
    return config.get_main_option("sqlalchemy.url") or ""


def run_migrations_offline() -> None:
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Override the ini's URL with the env-resolved one. We mutate a copy
    # of the section so alembic.ini stays the documented placeholder.
    section = config.get_section(config.config_ini_section, {}) or {}
    section["sqlalchemy.url"] = _resolve_url()

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
