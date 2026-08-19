from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from services.api.settings import settings


def direct_dsn() -> str:
    url = os.environ.get("DATABASE_URL_DIRECT", settings.database_url_direct)
    return url.replace("postgresql+psycopg://", "postgresql://").replace(
        "postgresql+asyncpg://", "postgresql://"
    )


async def register_codecs(conn: asyncpg.Connection) -> None:
    """Decode json/jsonb columns to real Python objects.

    asyncpg returns jsonb as a raw `str` unless a codec is registered. Without
    this, every jsonb column in the schema silently arrives as text:
    alert_source.config, channel.config, assistance_case.priority_factors
    (Rule 10's stored inputs), delivery_event.metadata, reach_prediction.features.

    This was a real, live-only bug: the ingestion registry did
    `dict(row["config"])` on alert_source.config and raised
    "dictionary update sequence element #0 has length 1; 2 is required" against
    the real database, while every fixture-based unit test passed — the
    fixtures were already dicts and never crossed the driver boundary. It is
    registered centrally here so it cannot be fixed in one call site and left
    broken in the other four.
    """
    for typename in ("json", "jsonb"):
        await conn.set_type_codec(
            typename,
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )


async def connect(dsn: str | None = None) -> asyncpg.Connection:
    """Single place every asyncpg connection is created, so codecs are never
    missed. Prefer this over calling asyncpg.connect() directly."""
    conn = await asyncpg.connect(dsn or direct_dsn())
    await register_codecs(conn)
    return conn


@asynccontextmanager
async def connect_direct() -> AsyncIterator[asyncpg.Connection]:
    conn = await connect()
    try:
        yield conn
    finally:
        await conn.close()


@asynccontextmanager
async def transaction(conn: asyncpg.Connection) -> AsyncIterator[asyncpg.Connection]:
    tr = conn.transaction()
    await tr.start()
    try:
        yield conn
        await tr.commit()
    except Exception:
        await tr.rollback()
        raise
