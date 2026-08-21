from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis

from services.api.auth import Principal
from services.api.deps import get_conn, get_idempotency_key, get_redis
from services.api.rbac import assert_delivery_in_scope, require_citizen_write
from services.api.schemas import AckRequest, AckResponse
from services.delivery.assurance import record
from services.delivery.ops_events import publish_ops
from services.delivery.state_machine import transition
from services.delivery.states import State

router = APIRouter(prefix="/api/v1", tags=["citizen"])


@router.post("/ack", response_model=AckResponse)
async def acknowledge(
    body: AckRequest,
    conn: asyncpg.Connection = Depends(get_conn),
    redis: Redis = Depends(get_redis),
    idempotency_key: str | None = Depends(get_idempotency_key),
    principal: Principal = Depends(require_citizen_write),
) -> AckResponse:
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header required")
    await assert_delivery_in_scope(conn, principal, body.delivery_id)
    existing = await conn.fetchval(
        """
        SELECT 1 FROM delivery_event
        WHERE delivery_id = $1 AND event_type = 'acknowledged'
        """,
        body.delivery_id,
    )
    if existing:
        return AckResponse(delivery_id=body.delivery_id, duplicate=True)
    delivery = await conn.fetchval("SELECT 1 FROM delivery WHERE id = $1", body.delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="delivery_not_found")
    inserted = await record(
        conn,
        body.delivery_id,
        "acknowledged",
        source="citizen",
        evidence_id=idempotency_key,
    )
    if inserted:
        await transition(conn, body.delivery_id, State.acknowledged, actor=principal.email)
        meta = await conn.fetchrow(
            """
            SELECT a.id AS alert_id, a.headline
            FROM delivery d
            JOIN alert a ON a.id = d.alert_id
            WHERE d.id = $1
            """,
            body.delivery_id,
        )
        if meta is not None:
            await publish_ops(
                redis,
                {
                    "type": "delivery.acknowledged",
                    "delivery_id": body.delivery_id,
                    "alert_id": meta["alert_id"],
                    "headline": meta["headline"],
                },
            )
    return AckResponse(delivery_id=body.delivery_id, duplicate=not inserted)
