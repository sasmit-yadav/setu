from __future__ import annotations

from collections.abc import AsyncGenerator

import asyncpg
from fastapi import Request
from redis.asyncio import Redis

from services.api.db import connect
from services.api.settings import settings


async def get_conn() -> AsyncGenerator[asyncpg.Connection, None]:
    # db.connect() (not asyncpg.connect) so the json/jsonb codec is registered
    # on every request connection — see the note in services/api/db.py.
    conn = await connect()
    try:
        yield conn
    finally:
        await conn.close()


async def get_redis() -> AsyncGenerator[Redis, None]:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


def get_idempotency_key(request: Request) -> str | None:
    return request.headers.get("Idempotency-Key")
