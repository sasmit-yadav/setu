from __future__ import annotations

import os

import psycopg


def db_url() -> str:
    url = os.environ.get("DATABASE_URL_DIRECT", "postgresql://setu:setu@localhost:5433/setu")
    return url.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+asyncpg://", "postgresql://")


def get_int(key: str) -> int:
    with psycopg.connect(db_url()) as conn:
        row = conn.execute("SELECT value FROM app_config WHERE key = %s", (key,)).fetchone()
    if row is None:
        raise KeyError(key)
    return int(row[0])
