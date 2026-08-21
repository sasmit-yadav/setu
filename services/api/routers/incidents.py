from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from services.api import config_repo
from services.api.auth import Principal
from services.api.deps import get_conn
from services.api.rbac import require_operational_read, require_state_admin
from services.api.schemas import IncidentDetailOut, IncidentSummaryOut, TimelineEventOut
from services.audit.after_action import after_action_report
from services.audit.ledger import append_audit
from services.audit.timeline import incident_detail, incident_timeline

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentSummaryOut])
async def list_incidents(
    limit: int | None = None,
    conn: asyncpg.Connection = Depends(get_conn),
    _principal: Principal = Depends(require_operational_read),
) -> list[IncidentSummaryOut]:
    effective_limit = (
        limit if limit is not None else await config_repo.get_int(conn, "api.list_default_limit")
    )
    rows = await conn.fetch(
        """
        SELECT i.id, i.label, i.incident_type, i.status, i.origin_source, i.opened_at,
               COUNT(a.id)::int AS version_count
        FROM incident i
        LEFT JOIN alert a ON a.incident_id = i.id
        GROUP BY i.id
        ORDER BY i.opened_at DESC
        LIMIT $1
        """,
        effective_limit,
    )
    return [
        IncidentSummaryOut(
            id=row["id"],
            label=row["label"],
            incident_type=row["incident_type"],
            status=row["status"],
            origin_source=row["origin_source"],
            opened_at=row["opened_at"].isoformat(),
            version_count=row["version_count"],
        )
        for row in rows
    ]


@router.get("/{incident_id}", response_model=IncidentDetailOut)
async def get_incident(
    incident_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
    _principal: Principal = Depends(require_operational_read),
) -> IncidentDetailOut:
    detail = await incident_detail(conn, incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="incident_not_found")
    return IncidentDetailOut(**detail)


@router.get("/{incident_id}/timeline", response_model=list[TimelineEventOut])
async def get_incident_timeline(
    incident_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
    _principal: Principal = Depends(require_operational_read),
) -> list[TimelineEventOut]:
    exists = await conn.fetchval("SELECT 1 FROM incident WHERE id = $1", incident_id)
    if not exists:
        raise HTTPException(status_code=404, detail="incident_not_found")
    events = await incident_timeline(conn, incident_id)
    return [TimelineEventOut(**event) for event in events]


@router.get("/{incident_id}/board")
async def incident_board(
    incident_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
    _principal: Principal = Depends(require_operational_read),
) -> dict:
    exists = await conn.fetchval("SELECT 1 FROM incident WHERE id = $1", incident_id)
    if not exists:
        raise HTTPException(status_code=404, detail="incident_not_found")
    worst_limit = await config_repo.get_int(conn, "board.worst_units_limit")
    closed = await config_repo.get_csv(conn, "assistance.status_sequence")
    closed_status = closed[-1] if closed else None
    reachability = await conn.fetch(
        """
        SELECT DISTINCT ON (rv.unit_id)
               rv.unit_id, rv.name, rv.geometry_level,
               rv.recipient_reach_pct, rv.population_reach_pct,
               rv.registered_recipients, rv.reached_recipients
        FROM v_reachability rv
        JOIN admin_unit u ON u.id = rv.unit_id
        JOIN alert a ON a.incident_id = $1 AND ST_Intersects(u.geom, a.area)
        ORDER BY rv.unit_id, rv.recipient_reach_pct NULLS LAST
        """,
        incident_id,
    )
    vulnerability = await conn.fetch(
        """
        SELECT cv.unit_id, cv.name, cv.primary_factors, cv.recommended_fallback,
               cv.historical_reach_pct
        FROM v_communication_vulnerability cv
        JOIN admin_unit u ON u.id = cv.unit_id
        JOIN alert a ON a.incident_id = $1 AND ST_Intersects(u.geom, a.area)
        ORDER BY COALESCE(cv.historical_reach_pct, 0) ASC, cv.name
        LIMIT $2
        """,
        incident_id,
        worst_limit,
    )
    no_relay = await conn.fetch(
        """
        SELECT DISTINCT u.id AS unit_id, u.name
        FROM admin_unit u
        JOIN alert a ON a.incident_id = $1 AND ST_Intersects(u.geom, a.area)
        WHERE NOT EXISTS (
            SELECT 1 FROM relay_node rn WHERE rn.unit_id = u.id AND rn.active
        )
        ORDER BY u.name
        """,
        incident_id,
    )
    queue_depth = await conn.fetchval(
        """
        SELECT COUNT(*)::int
        FROM assistance_case ac
        JOIN citizen_response cr ON cr.id = ac.citizen_response_id
        JOIN alert a ON a.id = cr.alert_id
        WHERE a.incident_id = $1
          AND ($2::text IS NULL OR ac.status <> $2)
        """,
        incident_id,
        closed_status,
    )
    human_confirmations = await conn.fetchval(
        """
        SELECT COUNT(*)::int
        FROM relay_confirmation rc
        JOIN delivery d ON d.id = rc.delivery_id
        JOIN alert a ON a.id = d.alert_id
        WHERE a.incident_id = $1 AND rc.confirmed_by_human
        """,
        incident_id,
    )
    channels = await conn.fetch(
        """
        SELECT c.code AS channel_code,
               COUNT(*)::int AS deliveries,
               COUNT(*) FILTER (WHERE d.simulated)::int AS simulated,
               COALESCE(MAX(assurance_level(d.id)), -1) AS max_assurance
        FROM delivery d
        JOIN channel c ON c.id = d.channel_id
        JOIN alert a ON a.id = d.alert_id
        WHERE a.incident_id = $1
        GROUP BY c.code
        ORDER BY c.code
        """,
        incident_id,
    )
    return {
        "incident_id": incident_id,
        "queue_depth": int(queue_depth or 0),
        "human_confirmations": int(human_confirmations or 0),
        "reachability": [
            {
                "unit_id": row["unit_id"],
                "name": row["name"],
                "geometry_level": row["geometry_level"],
                "recipient_reach_pct": float(row["recipient_reach_pct"])
                if row["recipient_reach_pct"] is not None
                else None,
                "population_reach_pct": float(row["population_reach_pct"])
                if row["population_reach_pct"] is not None
                else None,
                "registered_recipients": row["registered_recipients"] or 0,
                "reached_recipients": row["reached_recipients"] or 0,
            }
            for row in reachability
        ],
        "worst_units": [
            {
                "unit_id": row["unit_id"],
                "name": row["name"],
                "primary_factors": list(row["primary_factors"] or []),
                "recommended_fallback": row["recommended_fallback"],
                "historical_reach_pct": float(row["historical_reach_pct"])
                if row["historical_reach_pct"] is not None
                else None,
            }
            for row in vulnerability
        ],
        "no_relay_coverage": [
            {"unit_id": row["unit_id"], "name": row["name"]} for row in no_relay
        ],
        "channels": [
            {
                "channel_code": row["channel_code"],
                "deliveries": row["deliveries"],
                "simulated": row["simulated"],
                "max_assurance": row["max_assurance"],
            }
            for row in channels
        ],
    }


@router.get("/{incident_id}/after-action")
async def incident_after_action(
    incident_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
    _principal: Principal = Depends(require_operational_read),
) -> dict:
    report = await after_action_report(conn, incident_id)
    if report is None:
        raise HTTPException(status_code=404, detail="incident_not_found")
    return report


@router.post("/{incident_id}/close")
async def close_incident(
    incident_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_state_admin),
) -> dict:
    row = await conn.fetchrow(
        """
        UPDATE incident
        SET status = 'closed', closed_at = COALESCE(closed_at, now())
        WHERE id = $1
        RETURNING id, status, closed_at
        """,
        incident_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="incident_not_found")
    await append_audit(
        conn,
        incident_id=incident_id,
        event_type="incident.closed",
        payload={"status": row["status"]},
        actor=principal.email,
    )
    return {
        "incident_id": row["id"],
        "status": row["status"],
        "closed_at": row["closed_at"].isoformat() if row["closed_at"] else None,
    }
