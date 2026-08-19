from __future__ import annotations

import asyncpg


async def by_provider_ref(conn: asyncpg.Connection, provider_ref: str) -> int | None:
    value = await conn.fetchval(
        "SELECT id FROM delivery WHERE provider_ref = $1 ORDER BY id DESC LIMIT 1",
        provider_ref,
    )
    return int(value) if value is not None else None


async def delivery_channel_code(conn: asyncpg.Connection, delivery_id: int) -> str | None:
    return await conn.fetchval(
        """
        SELECT c.code FROM delivery d
        JOIN channel c ON c.id = d.channel_id
        WHERE d.id = $1
        """,
        delivery_id,
    )
