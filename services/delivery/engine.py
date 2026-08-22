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
from services.ml.reach_risk import predict_for_alert
from services.targeting.escalation import resolve_channels_for_recipients
from services.targeting.geo import recipients_in_area


async def _insert_delivery(
    conn: asyncpg.Connection,
    alert_id: int,
    recipient_id: int,
    channel_id: int,
    simulated: bool,
) -> int:
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
        simulated,
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
    return int(delivery_id)


async def _extreme_phone_channel_ids(conn: asyncpg.Connection) -> tuple[int | None, int | None, int | None]:
    rows = await conn.fetch("SELECT id, code FROM channel WHERE code = ANY($1::text[])", ["sms", "ivr", "fcm"])
    by_code = {str(r["code"]): int(r["id"]) for r in rows}
    return by_code.get("sms"), by_code.get("ivr"), by_code.get("fcm")


async def create_deliveries(conn: asyncpg.Connection, alert_id: int, recipient_ids: list[int]) -> list[int]:
    # Channel is resolved PER RECIPIENT, not once for the whole alert — see
    # resolve_channels_for_recipients for why (§8.5's real-phones-vs-simulated
    # split cannot be expressed by a single channel choice).
    resolved = await resolve_channels_for_recipients(conn, alert_id, recipient_ids)
    severity = await conn.fetchval("SELECT severity FROM alert WHERE id = $1", alert_id)
    sms_id, ivr_id, fcm_id = await _extreme_phone_channel_ids(conn)
    delivery_ids: list[int] = []
    for recipient_id in recipient_ids:
        channel_id, simulated = resolved[recipient_id]
        plans: list[tuple[int, bool]] = [(channel_id, simulated)]
        # Extreme: SMS + IVR are compulsory for every numbered phone, whether
        # or not they opened the citizen app. Push is extra when a token exists.
        if str(severity) == "extreme" and not simulated:
            rec = await conn.fetchrow(
                """
                SELECT (push_token IS NOT NULL) AS has_push,
                       (phone_enc IS NOT NULL) AS has_phone
                FROM recipient WHERE id = $1
                """,
                recipient_id,
            )
            if rec and rec["has_phone"]:
                if sms_id is not None:
                    plans.append((sms_id, False))
                if ivr_id is not None:
                    plans.append((ivr_id, False))
            if rec and rec["has_push"] and fcm_id is not None:
                plans.append((fcm_id, False))
        seen: set[int] = set()
        for cid, sim in plans:
            if cid in seen:
                continue
            seen.add(cid)
            delivery_ids.append(
                await _insert_delivery(conn, alert_id, recipient_id, cid, sim)
            )
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
        try:
            async with conn.transaction():
                await ensure_dispatch_allowed(conn, alert_id)
                await predict_for_alert(conn, alert_id)
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
                    raise DispatchError(
                        "no_recipients", "No consented recipients intersect the alert area"
                    )
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
        except QualityGateBlocked as blocked:
            # Audited OUTSIDE the transaction on purpose: the raise rolls the
            # transaction back, so an append_audit() before it would vanish
            # along with the dispatch. A blocked dispatch is exactly the event
            # the timeline must show (Part 16 Day 6 names alert.validation_failed
            # as a required timeline entry), so it is recorded after the rollback.
            await append_audit(
                conn,
                alert_id=alert_id,
                event_type="alert.validation_failed",
                payload={"failures": blocked.failures},
                actor=actor,
            )
            raise
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
