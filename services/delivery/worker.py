from __future__ import annotations

import asyncio
import json
import uuid

import asyncpg
import structlog
from redis.asyncio import Redis

from services.api import config_repo
from services.api.db import connect_direct, transaction
from services.api.settings import settings
from services.crypto.alert_signing import sign_payload
from services.delivery.channels.base import (
    ChannelUnavailable,
    OutboundMessage,
    TransientChannelError,
)
from services.delivery.channels.registry import load_channel_adapters
from services.delivery.fatigue import apply_headline
from services.delivery.keys import keys
from services.delivery.ops_events import publish_ops
from services.delivery.receipts import store_nonce
from services.delivery.relay_escalation import on_channels_exhausted
from services.delivery.state_machine import transition
from services.delivery.states import State
from services.ml.translate import resolve_alert_text

logger = structlog.get_logger(__name__)

PHONE_CHANNELS = frozenset({"sms", "ivr", "human_relay"})

# A unit conversion, not a tunable — "how many milliseconds are in a second"
# is not a policy decision anyone could reasonably want different, which is
# the test Part 38 gives for what belongs in config vs. what stays in code.
MS_PER_SECOND = 1000


async def ensure_consumer_group(redis: Redis, conn: asyncpg.Connection) -> None:
    stream = keys.stream_delivery()
    group = keys.group()
    try:
        await redis.xgroup_create(stream, group, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def _resolve_address(conn: asyncpg.Connection, row: asyncpg.Record) -> str:
    channel_code = row["channel_code"]
    if channel_code in PHONE_CHANNELS:
        if row["phone_enc"] and settings.pgcrypto_sym_key:
            phone = await conn.fetchval(
                "SELECT pgp_sym_decrypt($1, $2)",
                row["phone_enc"],
                settings.pgcrypto_sym_key,
            )
            if phone:
                return phone.decode() if isinstance(phone, bytes) else str(phone)
        raise ChannelUnavailable("recipient_no_phone")
    if channel_code == "fcm":
        if row["push_token"]:
            return row["push_token"]
        raise ChannelUnavailable("recipient_no_push_token")
    if channel_code == "email":
        if row["email_enc"] and settings.pgcrypto_sym_key:
            email = await conn.fetchval(
                "SELECT pgp_sym_decrypt($1, $2)",
                row["email_enc"],
                settings.pgcrypto_sym_key,
            )
            if email:
                return email.decode() if isinstance(email, bytes) else str(email)
        raise ChannelUnavailable("recipient_no_email")
    if row["push_token"]:
        return row["push_token"]
    return f"recipient:{row['recipient_id']}"


async def build_message(conn: asyncpg.Connection, delivery_id: int) -> OutboundMessage:
    row = await conn.fetchrow(
        """
        SELECT d.id, d.alert_id, d.recipient_id, c.code AS channel_code,
               a.headline, a.body, a.severity, a.effective_at, r.preferred_lang,
               r.push_token, r.kind, r.phone_enc, r.email_enc
        FROM delivery d
        JOIN alert a ON a.id = d.alert_id
        JOIN channel c ON c.id = d.channel_id
        JOIN recipient r ON r.id = d.recipient_id
        WHERE d.id = $1
        """,
        delivery_id,
    )
    if row is None:
        raise ValueError(f"delivery {delivery_id} not found")
    resolved = await resolve_alert_text(conn, row["alert_id"], row["preferred_lang"])
    headline, _ = await apply_headline(conn, row["alert_id"], resolved.headline)
    address = await _resolve_address(conn, row)
    signature = None
    if settings.alert_signing_seed_b64:
        signature = sign_payload(
            {
                "alert_id": row["alert_id"],
                "delivery_id": delivery_id,
                "headline": headline,
                "severity": row["severity"],
                "effective_at": row["effective_at"].isoformat(),
            }
        )
    return OutboundMessage(
        alert_id=row["alert_id"],
        delivery_id=row["id"],
        recipient_id=row["recipient_id"],
        channel_code=row["channel_code"],
        address=address,
        headline=headline,
        body=resolved.body,
        ack_url=f"{settings.public_base_url}/api/v1/ack",
        receipt_nonce=str(uuid.uuid4()),
        signature=signature,
    )


async def process_recipient(
    conn: asyncpg.Connection,
    redis: Redis,
    adapters: dict,
    alert_id: int,
    recipient_id: int,
) -> None:
    row = await conn.fetchrow(
        """
        SELECT d.id, d.state, c.code
        FROM delivery d
        JOIN channel c ON c.id = d.channel_id
        WHERE d.alert_id = $1 AND d.recipient_id = $2
          AND d.state IN ('pending', 'queued')
        ORDER BY d.attempt ASC, d.id ASC
        LIMIT 1
        """,
        alert_id,
        recipient_id,
    )
    if row is None:
        return
    delivery_id = row["id"]
    async with transaction(conn):
        if row["state"] == "pending":
            await transition(conn, delivery_id, State.queued)
        adapter = adapters.get(row["code"]) or adapters.get("sim")
        if adapter is None:
            raise RuntimeError("no adapter available")
        try:
            message = await build_message(conn, delivery_id)
            if message.receipt_nonce:
                await store_nonce(redis, conn, delivery_id, message.receipt_nonce)
            simulated = False
            try:
                result = await adapter.send(message)
            except ChannelUnavailable:
                if row["code"] not in ("human_relay", "sim"):
                    await on_channels_exhausted(
                        conn,
                        redis,
                        alert_id=alert_id,
                        recipient_id=recipient_id,
                        exhausted_delivery_id=delivery_id,
                    )
                sim = adapters.get("sim")
                if sim is None:
                    await transition(conn, delivery_id, State.failed, reason="channel_unavailable")
                    return
                result = await sim.send(message)
                simulated = True
            await transition(conn, delivery_id, State.sent, provider_ref=result.provider_ref)
            await conn.execute(
                """
                UPDATE delivery
                SET provider_ref = $2, simulated = $3
                WHERE id = $1
                """,
                delivery_id,
                result.provider_ref,
                result.simulated or simulated,
            )
            await transition(conn, delivery_id, State.delivered)
        except ChannelUnavailable as exc:
            await transition(conn, delivery_id, State.failed, reason=exc.code)
        except TransientChannelError as exc:
            await transition(conn, delivery_id, State.failed, reason=str(exc))


async def process_batch(conn: asyncpg.Connection, redis: Redis, fields: dict) -> None:
    alert_id = int(fields["alert_id"])
    recipient_ids = json.loads(fields["recipient_ids"])
    adapters = await load_channel_adapters(conn)
    for recipient_id in recipient_ids:
        await process_recipient(conn, redis, adapters, alert_id, int(recipient_id))
    await publish_ops(redis, {"type": "delivery.batch", "alert_id": alert_id})


async def worker_loop(consumer: str, shutdown: asyncio.Event | None = None) -> None:
    # Read the blocking window BEFORE building the Redis client: the client's
    # socket timeout must exceed XREADGROUP's block duration, or an idle
    # worker kills itself. redis-py's default socket_timeout is shorter than
    # delivery.xread_block_ms, so a worker with nothing to do raised
    # "TimeoutError: Timeout reading from localhost:6379" and exited — the
    # exact failure mode a delivery worker must never have, since "idle" is
    # its normal state between alerts.
    async with connect_direct() as conn:
        xread_count = await config_repo.get_int(conn, "delivery.xread_count")
        xread_block_ms = await config_repo.get_int(conn, "delivery.xread_block_ms")
        socket_timeout_grace_s = await config_repo.get_float(
            conn, "delivery.xread_socket_timeout_grace_s"
        )

    redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=(xread_block_ms / MS_PER_SECOND) + socket_timeout_grace_s,
    )
    async with connect_direct() as conn:
        await ensure_consumer_group(redis, conn)

    while shutdown is None or not shutdown.is_set():
        messages = await redis.xreadgroup(
            keys.group(),
            consumer,
            {keys.stream_delivery(): ">"},
            count=xread_count,
            block=xread_block_ms,
        )
        if not messages:
            continue
        for _, entries in messages:
            for msg_id, fields in entries:
                try:
                    async with connect_direct() as conn:
                        await process_batch(conn, redis, fields)
                    await redis.xack(keys.stream_delivery(), keys.group(), msg_id)
                except Exception:
                    logger.exception("batch_failed", msg_id=msg_id)


def main() -> None:
    asyncio.run(worker_loop(f"worker-{uuid.uuid4().hex[:8]}"))


if __name__ == "__main__":
    main()
