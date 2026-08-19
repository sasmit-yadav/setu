from __future__ import annotations

import asyncpg
from redis.asyncio import Redis

from services.api import config_repo
from services.delivery.assurance import record
from services.delivery.keys import keys
from services.delivery.state_machine import transition
from services.delivery.states import State

ALLOWED_RECEIPT_EVENTS = frozenset({"device_delivered", "notification_opened"})


async def store_nonce(redis: Redis, conn: asyncpg.Connection, delivery_id: int, nonce: str) -> None:
    ttl_minutes = await config_repo.get_int(conn, "assurance.receipt_nonce_ttl_minutes")
    seconds_per_minute = await config_repo.get_int(conn, "time.seconds_per_minute")
    await redis.set(keys.receipt_nonce(delivery_id), nonce, ex=ttl_minutes * seconds_per_minute)


async def nonce_valid(redis: Redis, delivery_id: int, nonce: str) -> bool:
    stored = await redis.get(keys.receipt_nonce(delivery_id))
    return stored is not None and stored == nonce


async def consume_nonce(redis: Redis, delivery_id: int, nonce: str) -> bool:
    if not await nonce_valid(redis, delivery_id, nonce):
        return False
    await redis.delete(keys.receipt_nonce(delivery_id))
    return True


async def record_receipt(
    conn: asyncpg.Connection,
    delivery_id: int,
    *,
    event_type: str,
    nonce: str,
    source: str = "service_worker",
) -> bool:
    if event_type not in ALLOWED_RECEIPT_EVENTS:
        raise ValueError(f"unsupported receipt event {event_type}")
    inserted = await record(
        conn,
        delivery_id,
        event_type,
        source=source,
        evidence_id=nonce,
    )
    if event_type == "device_delivered" and inserted:
        row = await conn.fetchrow("SELECT state FROM delivery WHERE id = $1", delivery_id)
        if row and row["state"] == "sent":
            await transition(conn, delivery_id, State.delivered, actor=source)
    return inserted
