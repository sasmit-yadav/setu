from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from services.api.db import connect, transaction


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: requires local Postgres")


@pytest_asyncio.fixture
async def db_conn() -> AsyncIterator[asyncpg.Connection]:
    # db.connect(), not raw asyncpg.connect() — tests must use the SAME
    # connection path as production, codecs included. Using a bare connection
    # here is precisely how the jsonb-returns-str bug passed every unit test
    # while live ingestion was broken.
    try:
        conn = await connect()
    except Exception as exc:
        pytest.skip(f"Postgres unavailable: {exc}")
    try:
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def delivery_row(db_conn: asyncpg.Connection) -> dict:
    async with transaction(db_conn):
        unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
        if unit_id is None:
            pytest.skip("admin_unit empty — run geometry pipeline first")
        recipient_id = await db_conn.fetchval(
            """
            INSERT INTO recipient (unit_id, kind, preferred_lang, consented_at)
            VALUES ($1, 'citizen', 'en', now())
            RETURNING id
            """,
            unit_id,
        )
        incident_id = await db_conn.fetchval(
            """
            INSERT INTO incident (label, incident_type, status, origin_source)
            VALUES ('TEST-INC', 'test', 'active', 'manual')
            RETURNING id
            """
        )
        alert_id = await db_conn.fetchval(
            """
            INSERT INTO alert (
                source_id, severity, headline, body, lang, area,
                effective_at, expires_at, raw_checksum, incident_id, lifecycle_status
            )
            SELECT 'manual', 'moderate', 'Test', 'Body', 'en', geom,
                   now(), now() + interval '1 hour', 'test-checksum', $1, 'active'
            FROM admin_unit WHERE id = $2
            RETURNING id
            """,
            incident_id,
            unit_id,
        )
        channel_id = await db_conn.fetchval("SELECT id FROM channel WHERE code = 'sim'")
        delivery_id = await db_conn.fetchval(
            """
            INSERT INTO delivery (alert_id, recipient_id, channel_id, state)
            VALUES ($1, $2, $3, 'pending')
            RETURNING id
            """,
            alert_id,
            recipient_id,
            channel_id,
        )
    row = await db_conn.fetchrow("SELECT * FROM delivery WHERE id = $1", delivery_id)
    assert row is not None
    return dict(row)
