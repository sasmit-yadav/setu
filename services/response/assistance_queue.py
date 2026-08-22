from __future__ import annotations

from typing import Any

import asyncpg
from redis.asyncio import Redis
from redis.exceptions import RedisError

from services.api.settings import settings
from services.audit.ledger import append_audit
from services.delivery.keys import keys

# geoBoundaries ADM3 and ADM5 are separate layers: every parent_id is NULL.
# Officers are scoped to Vythiri (ADM3); help cases sit on Muttil North (ADM5).
# The tree walk never sees that, so scope also allows intersecting geoms —
# same rule as assert_unit_in_scope.
_IN_OFFICER_SCOPE = """
              (
                {scope}::bigint IS NULL
                OR {unit} = {scope}
                OR {unit} IN (
                    WITH RECURSIVE descendants AS (
                        SELECT id FROM admin_unit WHERE id = {scope}
                        UNION ALL
                        SELECT child.id FROM admin_unit child
                        JOIN descendants d ON child.parent_id = d.id
                    )
                    SELECT id FROM descendants
                )
                OR EXISTS (
                    SELECT 1
                    FROM admin_unit scope
                    JOIN admin_unit target ON target.id = {unit}
                    WHERE scope.id = {scope}
                      AND ST_Intersects(scope.geom, target.geom)
                )
              )
"""


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
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        citizen_response_id,
        min(max(priority_score, 0.0), 1.0),
        priority_factors,
        model_version,
    )
    case_id = int(case_id)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.zadd(keys.zset_assistance(), {str(case_id): float(priority_score)})
    except (OSError, RedisError):
        return case_id
    finally:
        closer = getattr(redis, "aclose", None)
        if closer is not None:
            await closer()
        else:
            await redis.close()
    return case_id


async def rebuild_from_postgres(conn: asyncpg.Connection, redis: Redis) -> list[int]:
    rows = await conn.fetch(
        """
        SELECT id, priority_score
        FROM assistance_case
        WHERE status <> 'closed'
        ORDER BY priority_score DESC, created_at ASC
        """
    )
    key = keys.zset_assistance()
    await redis.delete(key)
    if rows:
        await redis.zadd(key, {str(row["id"]): float(row["priority_score"]) for row in rows})
    return [int(row["id"]) for row in rows]


_CASE_SELECT = """
            SELECT ac.*, cr.response_type, cr.alert_id, cr.unit_id, u.name AS unit_name,
                   cr.free_text, ch.code AS channel_code,
                   ST_Y(cr.location::geometry) AS lat,
                   ST_X(cr.location::geometry) AS lon
            FROM assistance_case ac
            JOIN citizen_response cr ON cr.id = ac.citizen_response_id
            JOIN admin_unit u ON u.id = cr.unit_id
            JOIN delivery d ON d.id = cr.delivery_id
            JOIN channel ch ON ch.id = d.channel_id
"""


async def list_cases(
    conn: asyncpg.Connection,
    *,
    status: str | None = "new",
    limit: int,
    scope_unit_id: int | None = None,
) -> list[dict[str, Any]]:
    if status:
        rows = await conn.fetch(
            f"""
            {_CASE_SELECT}
            WHERE ac.status = $1
              AND {_IN_OFFICER_SCOPE.format(unit="cr.unit_id", scope="$3")}
            ORDER BY ac.priority_score DESC, ac.created_at ASC
            LIMIT $2
            """,
            status,
            limit,
            scope_unit_id,
        )
    else:
        rows = await conn.fetch(
            f"""
            {_CASE_SELECT}
            WHERE {_IN_OFFICER_SCOPE.format(unit="cr.unit_id", scope="$2")}
            ORDER BY ac.priority_score DESC, ac.created_at ASC
            LIMIT $1
            """,
            limit,
            scope_unit_id,
        )
    return [dict(row) for row in rows]


async def get_case(conn: asyncpg.Connection, case_id: int) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        f"""
        {_CASE_SELECT}
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
    assigned_by: int,
    actor: str,
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
        actor=actor,
    )
    updated = await get_case(conn, case_id)
    assert updated is not None
    return updated


async def advance_status(
    conn: asyncpg.Connection,
    case_id: int,
    *,
    next_status: str,
    assigned_team: str | None,
    assigned_by: int | None,
    actor: str,
    sequence: list[str],
) -> dict[str, Any]:
    existing = await get_case(conn, case_id)
    if existing is None:
        raise KeyError(case_id)
    current = existing["status"]
    if current not in sequence or next_status not in sequence:
        raise ValueError("invalid_status")
    if sequence.index(next_status) != sequence.index(current) + 1:
        raise ValueError("invalid_transition")
    team = assigned_team or existing.get("assigned_team")
    closed = sequence[-1]
    assigned = sequence[1] if len(sequence) > 1 else sequence[0]
    if next_status != sequence[0] and not team:
        raise ValueError("assigned_team_required")
    if next_status == closed:
        row = await conn.fetchrow(
            """
            UPDATE assistance_case
            SET status = $2, assigned_team = $3, resolved_at = now()
            WHERE id = $1 AND status = $4
            RETURNING id
            """,
            case_id,
            next_status,
            team,
            current,
        )
    elif next_status == assigned:
        row = await conn.fetchrow(
            """
            UPDATE assistance_case
            SET status = $2, assigned_team = $3, assigned_by = $4
            WHERE id = $1 AND status = $5
            RETURNING id
            """,
            case_id,
            next_status,
            team,
            assigned_by,
            current,
        )
    else:
        row = await conn.fetchrow(
            """
            UPDATE assistance_case
            SET status = $2, assigned_team = $3
            WHERE id = $1 AND status = $4
            RETURNING id
            """,
            case_id,
            next_status,
            team,
            current,
        )
    if row is None:
        raise ValueError("invalid_transition")
    cr = await conn.fetchrow(
        "SELECT alert_id FROM citizen_response WHERE id = $1",
        existing["citizen_response_id"],
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
        event_type=f"assistance.{next_status}",
        payload={"case_id": case_id, "from": current, "to": next_status, "assigned_team": team},
        actor=actor,
    )
    updated = await get_case(conn, case_id)
    assert updated is not None
    return updated
