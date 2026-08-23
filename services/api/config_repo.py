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


async def get_localised(
    conn: asyncpg.Connection, key: str, lang: str | None
) -> str | None:
    """`key.<lang>` if it exists, else the base `key`.

    Outbound citizen-facing text has to follow the language the alert was
    resolved into. A Malayalam warning that ends in an English instruction line
    fails the same "understood in that village's language" claim the whole
    translation path exists to make.

    Falls back rather than raising: a language with no translated string still
    gets the base wording, which is worse than a translation but far better
    than an SMS that never goes out.
    """
    if lang:
        value = await get(conn, f"{key}.{lang}")
        if value:
            return value
    return await get(conn, key)
