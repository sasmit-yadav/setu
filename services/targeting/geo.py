from __future__ import annotations

import asyncpg


async def recipients_in_area(conn: asyncpg.Connection, alert_id: int) -> list[int]:
    """Everyone a dispatch should attempt automatically.

    Village hardware is excluded. A siren wakes a whole village at three in the
    morning, so firing one is a decision an officer takes on a named warning -
    the same reason a feed cannot dispatch and a runner is suggested rather than
    sent. It used to ride along on every Send simply because it was a recipient
    row, which also made a device count as one of the "people we will warn".
    POST /alerts/{id}/siren is how it goes off now.
    """
    rows = await conn.fetch(
        """
        WITH devices AS (
          SELECT COALESCE(
                   (SELECT string_to_array(value, ',') FROM app_config
                     WHERE key = 'recipient.device_kinds'),
                   ARRAY[]::text[]
                 ) AS kinds
        )
        SELECT DISTINCT r.id
        FROM recipient r
        CROSS JOIN devices
        JOIN admin_unit u ON u.id = r.unit_id
        JOIN alert a ON a.id = $1
        WHERE ST_Intersects(u.geom, a.area)
          AND r.consented_at IS NOT NULL
          AND r.opted_out_at IS NULL
          AND NOT (r.kind = ANY (devices.kinds))
        """,
        alert_id,
    )
    return [int(row["id"]) for row in rows]


async def device_recipients_in_area(
    conn: asyncpg.Connection, alert_id: int, kind: str
) -> list[int]:
    """Village hardware of one kind inside the alert area, for a manual trigger."""
    rows = await conn.fetch(
        """
        SELECT DISTINCT r.id
        FROM recipient r
        JOIN admin_unit u ON u.id = r.unit_id
        JOIN alert a ON a.id = $1
        WHERE ST_Intersects(u.geom, a.area)
          AND r.kind = $2
          AND r.opted_out_at IS NULL
        """,
        alert_id,
        kind,
    )
    return [int(row["id"]) for row in rows]


async def target_count(conn: asyncpg.Connection, alert_id: int) -> int:
    return len(await recipients_in_area(conn, alert_id))
