from __future__ import annotations

import json
from typing import Any

import asyncpg

from services.audit.ledger import append_audit
from services.delivery.state_machine import transition
from services.delivery.states import State

ASSURANCE_TO_STATE: dict[str, State | None] = {
    "delivery_attempted": None,
    "provider_accepted": None,
    "device_delivered": None,
    "notification_opened": None,
    "acknowledged": State.acknowledged,
    "citizen_response": None,
}

EVENT_TO_CAPABILITY_TIER = {
    "provider_accepted": "provider_accept",
    "device_delivered": "device_delivered",
    "notification_opened": "opened",
    "acknowledged": "acknowledgement",
}


async def record(
    conn: asyncpg.Connection,
    delivery_id: int,
    event_type: str,
    *,
    source: str,
    evidence_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    cap_tier = EVENT_TO_CAPABILITY_TIER.get(event_type)
    if cap_tier is not None:
        supported = await conn.fetchval(
            """
            SELECT t.supported
            FROM delivery d
            JOIN channel_capability_tier t ON t.channel_id = d.channel_id
            WHERE d.id = $1 AND t.tier = $2
            """,
            delivery_id,
            cap_tier,
        )
        if supported is not True:
            return False
    inserted = await conn.fetchval(
        """
        INSERT INTO delivery_event (delivery_id, event_type, source, evidence_id, metadata)
        VALUES ($1, $2::assurance_event, $3, $4, $5::jsonb)
        ON CONFLICT (delivery_id, event_type) DO NOTHING
        RETURNING id
        """,
        delivery_id,
        event_type,
        source,
        evidence_id,
        json.dumps(metadata or {}),
    )
    if inserted is None:
        return False
    mapped = ASSURANCE_TO_STATE[event_type]
    if mapped is State.acknowledged:
        await transition(conn, delivery_id, mapped, actor=source)
    row = await conn.fetchrow(
        """
        SELECT d.alert_id, a.incident_id
        FROM delivery d
        JOIN alert a ON a.id = d.alert_id
        WHERE d.id = $1
        """,
        delivery_id,
    )
    if row is not None:
        await append_audit(
            conn,
            alert_id=row["alert_id"],
            incident_id=row["incident_id"],
            delivery_id=delivery_id,
            event_type="delivery.assurance_advanced",
            payload={"assurance_event": event_type, "source": source},
            actor=source,
        )
    return True
