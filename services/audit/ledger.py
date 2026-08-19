from __future__ import annotations

import hashlib
import json
from typing import Any

import asyncpg

GENESIS_HASH = "0" * 64


def _canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


async def append_audit(
    conn: asyncpg.Connection,
    *,
    event_type: str,
    payload: dict[str, Any],
    alert_id: int | None = None,
    delivery_id: int | None = None,
    incident_id: int | None = None,
    actor: str | None = None,
) -> str:
    prev_hash = await conn.fetchval(
        "SELECT hash FROM audit_event ORDER BY id DESC LIMIT 1"
    )
    if prev_hash is None:
        prev_hash = GENESIS_HASH
    body = _canonical_payload(payload)
    digest = hashlib.sha256(f"{prev_hash}{body}".encode()).hexdigest()
    await conn.execute(
        """
        INSERT INTO audit_event (
            alert_id, delivery_id, incident_id, event_type,
            payload, actor, prev_hash, hash
        )
        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8)
        """,
        alert_id,
        delivery_id,
        incident_id,
        event_type,
        body,
        actor,
        prev_hash,
        digest,
    )
    return digest
