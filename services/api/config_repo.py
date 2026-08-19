from __future__ import annotations

import asyncpg


async def get(conn: asyncpg.Connection, key: str) -> str | None:
    return await conn.fetchval("SELECT value FROM app_config WHERE key = $1", key)


async def get_bool(conn: asyncpg.Connection, key: str) -> bool:
    value = await get(conn, key)
    return value is not None and value.lower() in ("true", "1", "yes")


async def get_int(conn: asyncpg.Connection, key: str) -> int:
    value = await get(conn, key)
    if value is None:
        raise KeyError(key)
    return int(value)


async def get_float(conn: asyncpg.Connection, key: str) -> float:
    value = await get(conn, key)
    if value is None:
        raise KeyError(key)
    return float(value)


async def get_str(conn: asyncpg.Connection, key: str) -> str:
    value = await get(conn, key)
    if value is None:
        raise KeyError(key)
    return value


async def get_csv(conn: asyncpg.Connection, key: str) -> list[str]:
    raw = await get_str(conn, key)
    return [part.strip() for part in raw.split(",") if part.strip()]
