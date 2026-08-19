from __future__ import annotations

import asyncpg


async def primary_channel_for_alert(conn: asyncpg.Connection, alert_id: int) -> int:
    severity = await conn.fetchval("SELECT severity FROM alert WHERE id = $1", alert_id)
    row = await conn.fetchrow(
        """
        SELECT channel_id
        FROM escalation_policy
        WHERE severity = $1
        ORDER BY step_order ASC
        LIMIT 1
        """,
        severity,
    )
    if row is None:
        raise ValueError(f"no escalation policy for severity {severity}")
    return int(row["channel_id"])
