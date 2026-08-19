from __future__ import annotations

import json
from typing import Any

import asyncpg

from services.audit.ledger import append_audit


async def create_case(
    conn: asyncpg.Connection,
    *,
    citizen_response_id: int,
    priority_score: float,
    priority_factors: dict[str, Any],
) -> int:
    model_version = str(priority_factors.get("weight_version", "unknown"))
    case_id = await conn.fetchval(
        """
        INSERT INTO assistance_case (
            citizen_response_id, priority_score, priority_factors, model_version
        )
        VALUES ($1, $2, $3::jsonb, $4)
        RETURNING id
        """,
        citizen_response_id,
        min(max(priority_score, 0.0), 1.0),
        json.dumps(priority_factors),
        model_version,
    )
    return int(case_id)


async def list_cases(
    conn: asyncpg.Connection,
    *,
    status: str | None = "new",
    limit: int,
) -> list[dict[str, Any]]:
    if status:
        rows = await conn.fetch(
            """
            SELECT ac.*, cr.response_type, cr.alert_id, cr.unit_id, u.name AS unit_name
            FROM assistance_case ac
            JOIN citizen_response cr ON cr.id = ac.citizen_response_id
            JOIN admin_unit u ON u.id = cr.unit_id
            WHERE ac.status = $1
            ORDER BY ac.priority_score DESC, ac.created_at ASC
            LIMIT $2
            """,
            status,
            limit,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT ac.*, cr.response_type, cr.alert_id, cr.unit_id, u.name AS unit_name
            FROM assistance_case ac
            JOIN citizen_response cr ON cr.id = ac.citizen_response_id
            JOIN admin_unit u ON u.id = cr.unit_id
            ORDER BY ac.priority_score DESC, ac.created_at ASC
            LIMIT $1
            """,
            limit,
        )
    return [dict(row) for row in rows]


async def get_case(conn: asyncpg.Connection, case_id: int) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """
        SELECT ac.*, cr.response_type, cr.alert_id, cr.unit_id, u.name AS unit_name,
               cr.free_text, cr.location_consent
        FROM assistance_case ac
        JOIN citizen_response cr ON cr.id = ac.citizen_response_id
        JOIN admin_unit u ON u.id = cr.unit_id
        WHERE ac.id = $1
        """,
        case_id,
    )
    return dict(row) if row else None


async def assign_case(
    conn: asyncpg.Connection,
    case_id: int,
    *,
    assigned_team: str,
    assigned_by: int | None = None,
) -> dict[str, Any]:
    row = await conn.fetchrow(
        """
        UPDATE assistance_case
        SET status = 'assigned', assigned_team = $2, assigned_by = $3
        WHERE id = $1 AND status = 'new'
        RETURNING id, citizen_response_id
        """,
        case_id,
        assigned_team,
        assigned_by,
    )
    if row is None:
        existing = await get_case(conn, case_id)
        if existing is None:
            raise KeyError(case_id)
        raise ValueError("case_not_assignable")
    cr = await conn.fetchrow(
        "SELECT alert_id FROM citizen_response WHERE id = $1",
        row["citizen_response_id"],
    )
    incident_id = None
    if cr:
        incident_id = await conn.fetchval(
            "SELECT incident_id FROM alert WHERE id = $1",
            cr["alert_id"],
        )
    await append_audit(
        conn,
        alert_id=cr["alert_id"] if cr else None,
        incident_id=incident_id,
        event_type="assistance.assigned",
        payload={"case_id": case_id, "assigned_team": assigned_team},
        actor=str(assigned_by) if assigned_by else "api",
    )
    updated = await get_case(conn, case_id)
    assert updated is not None
    return updated
