from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.api import config_repo
from services.api.auth import Principal
from services.api.deps import get_conn
from services.api.rbac import (
    OFFICER,
    RELAY_NODE,
    STATE_ADMIN,
    assert_unit_in_scope,
    require_relay_confirm,
    require_relay_summary,
)
from services.api.settings import settings
from services.audit.ledger import append_audit
from services.crypto.alert_signing import verify_payload
from services.delivery.assurance import record
from services.delivery.channels.human_relay import (
    confirm_relay_delivery,
    find_relay_node,
)
from services.ml.translate import lang_for_unit, resolve_alert_text

router = APIRouter(prefix="/api/v1/relay", tags=["relay"])


async def _unit_contacts(
    conn: asyncpg.Connection, unit_id: int, may_dial: bool
) -> list[dict]:
    """Every active relay contact for a unit, in the order the dispatcher ranks them.

    Same ordering as find_relay_node (relay.node_kind_priority, then distance up
    the admin tree) so the head of this list is always the node that would
    actually be called — the screen and the dispatcher cannot disagree.

    Numbers follow the same rule as the single contact: officers and state admins
    can dial, an auditor or a relay contact reading the queue cannot see other
    people's lines.
    """
    kinds = await config_repo.get_csv(conn, "relay.node_kind_priority")
    rows = await conn.fetch(
        """
        WITH RECURSIVE chain AS (
            SELECT id, parent_id, 0 AS depth FROM admin_unit WHERE id = $1
            UNION ALL
            SELECT u.id, u.parent_id, chain.depth + 1
            FROM admin_unit u
            JOIN chain ON u.id = chain.parent_id
        )
        SELECT rn.id, rn.kind, rn.name, rn.phone_enc
        FROM relay_node rn
        JOIN chain c ON c.id = rn.unit_id
        WHERE rn.active
        ORDER BY array_position($2::text[], rn.kind), c.depth, rn.id
        """,
        unit_id,
        kinds,
    )
    out: list[dict] = []
    for row in rows:
        phone = None
        if may_dial and row["phone_enc"] and settings.pgcrypto_sym_key:
            try:
                raw = await conn.fetchval(
                    "SELECT pgp_sym_decrypt($1, $2)",
                    row["phone_enc"],
                    settings.pgcrypto_sym_key,
                )
            except asyncpg.PostgresError:
                # Sealed with a different key — show the name without a number
                # rather than failing the queue, same as the single-contact path.
                raw = None
            if raw:
                phone = raw.decode() if isinstance(raw, bytes) else str(raw)
        out.append(
            {
                "id": int(row["id"]),
                "kind": row["kind"],
                "name": row["name"],
                "phone": phone,
            }
        )
    return out


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
        # Name the person this task is actually for. The desk was showing the
        # village and the warning but not who to ring, which leaves the officer
        # holding a task with no addressee. Resolved through the same
        # find_relay_node the dispatcher uses, so the screen and the call agree
        # on who was chosen — including the kind priority that picked them.
        # The number itself stays out: a relay volunteer's line is not something
        # every operational-read role needs on screen.
        node = await find_relay_node(conn, int(row["unit_id"]))
        # The number is for whoever has to place the call. An auditor works from
        # aggregates, and a relay contact reading this queue does not need other
        # contacts' lines - the same reason assistance summaries give them a
        # count and an area instead of a list.
        contact_phone = None
        may_dial = principal.role in (OFFICER, STATE_ADMIN)
        if (
            node is not None
            and may_dial
            and node["phone_enc"]
            and settings.pgcrypto_sym_key
        ):
            try:
                raw = await conn.fetchval(
                    "SELECT pgp_sym_decrypt($1, $2)",
                    node["phone_enc"],
                    settings.pgcrypto_sym_key,
                )
            except asyncpg.PostgresError:
                # Sealed with a different key - pgp_sym_decrypt raises rather
                # than returning NULL. Show the name without a number instead of
                # failing the whole queue, which is what the seed's 'CHANGE-ME'
                # rows used to do to the human_relay adapter.
                raw = None
            if raw:
                contact_phone = raw.decode() if isinstance(raw, bytes) else str(raw)
        out.append(
            {
                "id": row["id"],
                "alert_id": row["alert_id"],
                "state": row["state"],
                "unit_id": row["unit_id"],
                "unit_name": row["unit_name"],
                "contact_name": node["name"] if node else None,
                "contact_kind": node["kind"] if node else None,
                "contact_phone": contact_phone,
                # find_relay_node returns the ONE node the dispatcher would pick,
                # which left the desk naming a single contact — while the spoken
                # pitch promises "panchayat, police, ASHA". A runner task is not
                # one phone call: if a village is unreachable you ring everyone
                # who can walk there. So the whole ordered list travels too, and
                # contact_* above stays as the head of it for anything already
                # reading those fields.
                "contacts": await _unit_contacts(conn, int(row["unit_id"]), may_dial),
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
