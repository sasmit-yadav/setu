from __future__ import annotations

import json
from typing import Any

import asyncpg

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


async def record(
    conn: asyncpg.Connection,
    delivery_id: int,
    event_type: str,
    *,
    source: str,
    evidence_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
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
    return True
