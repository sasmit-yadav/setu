from __future__ import annotations

import asyncpg


async def recipients_in_area(conn: asyncpg.Connection, alert_id: int) -> list[int]:
    rows = await conn.fetch(
        """
        SELECT DISTINCT r.id
        FROM recipient r
        JOIN admin_unit u ON u.id = r.unit_id
        JOIN alert a ON a.id = $1
        WHERE ST_Intersects(u.geom, a.area)
          AND r.consented_at IS NOT NULL
          AND r.opted_out_at IS NULL
        """,
        alert_id,
    )
    return [int(row["id"]) for row in rows]


async def target_count(conn: asyncpg.Connection, alert_id: int) -> int:
    return len(await recipients_in_area(conn, alert_id))
