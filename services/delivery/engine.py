from __future__ import annotations

import json

import asyncpg
from redis.asyncio import Redis

from services.api import config_repo
from services.audit.ledger import append_audit
from services.delivery.channels.registry import chunked
from services.delivery.keys import keys
from services.governance.approvals import ensure_dispatch_allowed
from services.governance.quality_gate import (
    has_blocking_failure,
    persist_results,
    validate,
)
from services.governance.versioning import (
    VersionInFlightError,
    acquire_supersede_lock,
    release_supersede_lock,
    supersede_predecessor,
)
from services.targeting.escalation import primary_channel_for_alert
from services.targeting.geo import recipients_in_area


async def create_deliveries(conn: asyncpg.Connection, alert_id: int, recipient_ids: list[int]) -> list[int]:
    channel_id = await primary_channel_for_alert(conn, alert_id)
    sim_channel_id = await conn.fetchval("SELECT id FROM channel WHERE code = 'sim'")
    delivery_ids: list[int] = []
    for recipient_id in recipient_ids:
        delivery_id = await conn.fetchval(
            """
            INSERT INTO delivery (alert_id, recipient_id, channel_id, state, simulated)
            VALUES ($1, $2, $3, 'pending', $4)
            ON CONFLICT (alert_id, recipient_id, channel_id, attempt) DO NOTHING
            RETURNING id
            """,
            alert_id,
            recipient_id,
            channel_id,
            channel_id == sim_channel_id,
        )
        if delivery_id is None:
            delivery_id = await conn.fetchval(
                """
                SELECT id FROM delivery
                WHERE alert_id = $1 AND recipient_id = $2 AND channel_id = $3 AND attempt = 1
                """,
                alert_id,
                recipient_id,
                channel_id,
            )
        delivery_ids.append(int(delivery_id))
    return delivery_ids


async def enqueue_fanout(redis: Redis, conn: asyncpg.Connection, alert_id: int, recipient_ids: list[int]) -> None:
    batch_size = await config_repo.get_int(conn, "delivery.batch_size")
    stream_maxlen = await config_repo.get_int(conn, "delivery.stream_maxlen")
    for chunk in chunked(recipient_ids, batch_size):
        await redis.xadd(
            keys.stream_delivery(),
            {"alert_id": str(alert_id), "recipient_ids": json.dumps(chunk)},
            maxlen=stream_maxlen,
            approximate=True,
        )


async def dispatch_alert(conn: asyncpg.Connection, redis: Redis, alert_id: int, *, actor: str) -> dict:
    incident_id = await conn.fetchval("SELECT incident_id FROM alert WHERE id = $1", alert_id)
    locked = False
    if incident_id is not None:
        locked = await acquire_supersede_lock(redis, conn, int(incident_id))
        if not locked:
            raise VersionInFlightError()
    try:
        async with conn.transaction():
            await ensure_dispatch_allowed(conn, alert_id)
            results = await validate(conn, alert_id)
            await persist_results(conn, alert_id, results)
            if has_blocking_failure(results):
                failures = [
                    {"rule_id": r.rule_id, "message": r.message}
                    for r in results
                    if r.status == "fail"
                ]
                raise QualityGateBlocked(failures)
            await supersede_predecessor(conn, alert_id, actor=actor)
            recipient_ids = await recipients_in_area(conn, alert_id)
            if not recipient_ids:
                raise DispatchError("no_recipients", "No consented recipients intersect the alert area")
            await create_deliveries(conn, alert_id, recipient_ids)
            await enqueue_fanout(redis, conn, alert_id, recipient_ids)
            await conn.execute(
                "UPDATE alert SET lifecycle_status = 'active' WHERE id = $1",
                alert_id,
            )
            await append_audit(
                conn,
                alert_id=alert_id,
                event_type="alert.dispatched",
                payload={"recipient_count": len(recipient_ids)},
                actor=actor,
            )
            return {"alert_id": alert_id, "recipient_count": len(recipient_ids)}
    finally:
        if locked and incident_id is not None:
            await release_supersede_lock(redis, int(incident_id))


class QualityGateBlocked(Exception):
    def __init__(self, failures: list[dict]) -> None:
        self.failures = failures


class DispatchError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
