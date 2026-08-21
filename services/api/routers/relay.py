from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.api import config_repo
from services.api.auth import Principal
from services.api.deps import get_conn
from services.api.rbac import (
    RELAY_NODE,
    assert_unit_in_scope,
    require_relay_confirm,
    require_relay_summary,
)
from services.audit.ledger import append_audit
from services.crypto.alert_signing import verify_payload
from services.delivery.assurance import record
from services.delivery.channels.human_relay import confirm_relay_delivery
from services.ml.translate import lang_for_unit, resolve_alert_text

router = APIRouter(prefix="/api/v1/relay", tags=["relay"])


class PeerReceiptRequest(BaseModel):
    delivery_id: int
    alert_id: int
    headline: str
    severity: str
    effective_at: str
    signature: str = Field(min_length=1)


@router.post("/receipt")
async def peer_relay_receipt(
    body: PeerReceiptRequest,
    conn: asyncpg.Connection = Depends(get_conn),
) -> dict:
    payload = {
        "alert_id": body.alert_id,
        "delivery_id": body.delivery_id,
        "headline": body.headline,
        "severity": body.severity,
        "effective_at": body.effective_at,
    }
    if not verify_payload(payload, body.signature):
        raise HTTPException(status_code=403, detail={"code": "invalid_signature"})
    row = await conn.fetchrow(
        "SELECT id, alert_id FROM delivery WHERE id = $1",
        body.delivery_id,
    )
    if row is None or int(row["alert_id"]) != body.alert_id:
        raise HTTPException(status_code=404, detail="delivery_not_found")
    incident_id = await conn.fetchval(
        "SELECT incident_id FROM alert WHERE id = $1",
        body.alert_id,
    )
    await record(
        conn,
        body.delivery_id,
        "device_delivered",
        source="peer_relay",
        evidence_id=body.signature,
    )
    hops = await config_repo.get_int(conn, "relay.peer_max_hops")
    await append_audit(
        conn,
        alert_id=body.alert_id,
        incident_id=incident_id,
        delivery_id=body.delivery_id,
        event_type="relay.peer_received",
        payload={"hops": hops},
        actor="community_relay",
    )
    return {"delivery_id": body.delivery_id, "recorded": True}


@router.get("/tasks")
async def list_relay_tasks(
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_relay_summary),
) -> list[dict]:
    own_unit = principal.unit_scope_id if principal.role == RELAY_NODE else None
    if principal.role == RELAY_NODE and own_unit is None:
        return []
    rows = await conn.fetch(
        """
        SELECT d.id, d.alert_id, d.state, r.unit_id, u.name AS unit_name,
               a.headline, a.severity
        FROM delivery d
        JOIN channel c ON c.id = d.channel_id
        JOIN recipient r ON r.id = d.recipient_id
        JOIN admin_unit u ON u.id = r.unit_id
        JOIN alert a ON a.id = d.alert_id
        WHERE c.code = 'human_relay'
          AND d.state IN ('pending', 'queued', 'sent')
          AND (
            $1::bigint IS NULL
            OR r.unit_id = $1
            OR EXISTS (
                WITH RECURSIVE descendants AS (
                    SELECT id FROM admin_unit WHERE id = $1
                    UNION ALL
                    SELECT child.id
                    FROM admin_unit child
                    JOIN descendants parent ON child.parent_id = parent.id
                )
                SELECT 1 FROM descendants WHERE id = r.unit_id
            )
          )
        ORDER BY d.id
        """,
        own_unit,
    )
    out: list[dict] = []
    for row in rows:
        lang = await lang_for_unit(conn, int(row["unit_id"]))
        resolved = await resolve_alert_text(conn, int(row["alert_id"]), lang)
        out.append(
            {
                "id": row["id"],
                "alert_id": row["alert_id"],
                "state": row["state"],
                "unit_id": row["unit_id"],
                "unit_name": row["unit_name"],
                "headline": resolved.headline,
                "body": resolved.body,
                "lang": resolved.lang,
                "translated": resolved.translated,
                "fallback_notice": resolved.fallback_notice,
                "severity": row["severity"],
            }
        )
    return out


@router.post("/tasks/{task_id}/confirm")
async def confirm_relay_task(
    task_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_relay_confirm),
) -> dict:
    unit_id = await conn.fetchval(
        """
        SELECT r.unit_id
        FROM delivery d
        JOIN recipient r ON r.id = d.recipient_id
        WHERE d.id = $1
        """,
        task_id,
    )
    if unit_id is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    await assert_unit_in_scope(conn, principal, int(unit_id))
    confirmed = await confirm_relay_delivery(
        conn,
        task_id,
        method="http",
        actor=principal.email,
    )
    if not confirmed:
        raise HTTPException(status_code=409, detail="relay_confirm_failed")
    return {"delivery_id": task_id, "confirmed": True}
