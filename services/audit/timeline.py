from __future__ import annotations

from typing import Any

import asyncpg


async def incident_timeline(conn: asyncpg.Connection, incident_id: int) -> list[dict[str, Any]]:
    exists = await conn.fetchval("SELECT 1 FROM incident WHERE id = $1", incident_id)
    if not exists:
        return []
    rows = await conn.fetch(
        """
        SELECT id, event_type, payload, actor, occurred_at,
               alert_id, delivery_id
        FROM audit_event
        WHERE incident_id = $1
        ORDER BY occurred_at ASC, id ASC
        """,
        incident_id,
    )
    return [
        {
            "id": row["id"],
            "event_type": row["event_type"],
            "payload": row["payload"],
            "actor": row["actor"],
            "occurred_at": row["occurred_at"].isoformat(),
            "alert_id": row["alert_id"],
            "delivery_id": row["delivery_id"],
        }
        for row in rows
    ]


async def incident_detail(conn: asyncpg.Connection, incident_id: int) -> dict[str, Any] | None:
    incident = await conn.fetchrow("SELECT * FROM incident WHERE id = $1", incident_id)
    if incident is None:
        return None
    versions = await conn.fetch(
        """
        SELECT id, version_number, severity, lifecycle_status, change_reason,
               supersedes_alert_id, effective_at, expires_at
        FROM alert
        WHERE incident_id = $1
        ORDER BY version_number ASC
        """,
        incident_id,
    )
    return {
        "id": incident["id"],
        "label": incident["label"],
        "incident_type": incident["incident_type"],
        "status": incident["status"],
        "origin_source": incident["origin_source"],
        "opened_at": incident["opened_at"].isoformat(),
        "versions": [
            {
                "id": row["id"],
                "version_number": row["version_number"],
                "severity": row["severity"],
                "lifecycle_status": row["lifecycle_status"],
                "change_reason": row["change_reason"],
                "supersedes_alert_id": row["supersedes_alert_id"],
                "effective_at": row["effective_at"].isoformat() if row["effective_at"] else None,
                "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
            }
            for row in versions
        ],
    }
