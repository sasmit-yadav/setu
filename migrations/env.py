"""migrations/env.py — Alembic runtime config.

Always runs against DATABASE_URL_DIRECT (Part 23), read straight from the
environment via python-dotenv, never from services.api.settings — migrations
must not depend on app boot succeeding, and must not depend on app_config
existing (Part 38's bootstrap exception applies here too).
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DIRECT_URL = os.environ.get(
    "DATABASE_URL_DIRECT", "postgresql://setu:setu@localhost:5433/setu"
)
# Force the psycopg3 dialect explicitly. A bare "postgresql://" (what Neon
# hands you, and what .env.example documents) defaults SQLAlchemy to
# psycopg2, which requirements.txt does not install — psycopg[binary] (v3)
# is the pinned driver. Rewriting here means .env.example can stay in the
# exact form Neon gives it, per Part 23's own instruction.
if DIRECT_URL.startswith("postgresql://"):
    DIRECT_URL = "postgresql+psycopg://" + DIRECT_URL[len("postgresql://"):]
config.set_main_option("sqlalchemy.url", DIRECT_URL)

target_metadata = None  # DDL is hand-written per migration (Part 5) — no ORM models to autogenerate from


def run_migrations_offline() -> None:
    context.configure(
        url=DIRECT_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
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
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
