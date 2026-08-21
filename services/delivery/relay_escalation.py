from __future__ import annotations

import json

import asyncpg
from redis.asyncio import Redis

from services.api import config_repo
from services.audit.ledger import append_audit
from services.delivery.channels.human_relay import find_relay_node
from services.delivery.keys import keys


async def on_channels_exhausted(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    alert_id: int,
    recipient_id: int,
    exhausted_delivery_id: int,
) -> int | None:
    if not await config_repo.get_bool(conn, "relay.escalate_on_channels_exhausted"):
        return None
    unit_id = await conn.fetchval("SELECT unit_id FROM recipient WHERE id = $1", recipient_id)
    if unit_id is None:
        return None
    human_id = await conn.fetchval("SELECT id FROM channel WHERE code = 'human_relay'")
    if human_id is None:
        return None
    existing = await conn.fetchval(
        """
        SELECT d.id
        FROM delivery d
        JOIN recipient r ON r.id = d.recipient_id
        WHERE d.alert_id = $1 AND d.channel_id = $2 AND r.unit_id = $3
        LIMIT 1
        """,
        alert_id,
        human_id,
        unit_id,
    )
    if existing is not None:
        return int(existing)
    incident_id = await conn.fetchval("SELECT incident_id FROM alert WHERE id = $1", alert_id)
    node = await find_relay_node(conn, int(unit_id))
    if node is None:
        await append_audit(
            conn,
            alert_id=alert_id,
            incident_id=incident_id,
            delivery_id=exhausted_delivery_id,
            event_type="relay.unavailable",
            payload={"unit_id": unit_id, "reason": "no_active_relay_node"},
            actor="delivery_worker",
        )
        return None
    delivery_id = await conn.fetchval(
        """
        INSERT INTO delivery (alert_id, recipient_id, channel_id, state, simulated)
        VALUES ($1, $2, $3, 'pending', false)
        RETURNING id
        """,
        alert_id,
        recipient_id,
        human_id,
    )
    stream_maxlen = await config_repo.get_int(conn, "delivery.stream_maxlen")
    await redis.xadd(
        keys.stream_delivery(),
        {"alert_id": str(alert_id), "recipient_ids": json.dumps([recipient_id])},
        maxlen=stream_maxlen,
        approximate=True,
    )
    await append_audit(
        conn,
        alert_id=alert_id,
        incident_id=incident_id,
        delivery_id=int(delivery_id),
        event_type="relay.task_created",
        payload={
            "unit_id": unit_id,
            "exhausted_delivery_id": exhausted_delivery_id,
            "relay_node_id": node["id"],
        },
        actor="delivery_worker",
    )
    return int(delivery_id)
