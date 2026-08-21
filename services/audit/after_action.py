from __future__ import annotations

from typing import Any

import asyncpg

from services.api import config_repo


async def after_action_report(conn: asyncpg.Connection, incident_id: int) -> dict[str, Any] | None:
    incident = await conn.fetchrow("SELECT * FROM incident WHERE id = $1", incident_id)
    if incident is None:
        return None
    reach_floor = await config_repo.get_float(conn, "reachability.reached_tier_floor")
    queue_depth = await conn.fetchval(
        """
        SELECT COUNT(*)::int
        FROM assistance_case ac
        JOIN citizen_response cr ON cr.id = ac.citizen_response_id
        JOIN alert a ON a.id = cr.alert_id
        WHERE a.incident_id = $1 AND ac.status <> 'closed'
        """,
        incident_id,
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
    unavailable = await conn.fetchval(
        """
        SELECT COUNT(*)::int FROM audit_event
        WHERE incident_id = $1 AND event_type = 'relay.unavailable'
        """,
        incident_id,
    )
    versions = await conn.fetchval(
        "SELECT COUNT(*)::int FROM alert WHERE incident_id = $1",
        incident_id,
    )
    deliveries = await conn.fetchval(
        """
        SELECT COUNT(*)::int
        FROM delivery d
        JOIN alert a ON a.id = d.alert_id
        WHERE a.incident_id = $1
        """,
        incident_id,
    )
    reached = await conn.fetchval(
        """
        SELECT COUNT(*)::int
        FROM delivery d
        JOIN alert a ON a.id = d.alert_id
        WHERE a.incident_id = $1 AND assurance_level(d.id) >= $2
        """,
        incident_id,
        int(reach_floor),
    )
    recs: list[dict[str, Any]] = [
        {
            "id": "open_assistance",
            "recommendation": (
                "Keep field teams assigned until the open assistance queue is empty."
                if queue_depth
                else "No open assistance cases remain — close staffing once after-action is filed."
            ),
            "measurement": "open_assistance_cases",
            "value": int(queue_depth or 0),
        },
        {
            "id": "human_relay",
            "recommendation": (
                "Human-relay confirmations occurred — keep those nodes active for the next incident."
                if human_confirmations
                else "No HUMAN confirmations were recorded — rehearse B9 before the next extreme alert."
            ),
            "measurement": "relay_confirmations",
            "value": int(human_confirmations or 0),
        },
        {
            "id": "relay_gap",
            "recommendation": (
                "Register an active relay_node for every unit that emitted relay.unavailable."
                if unavailable
                else "Every targeted unit had a registered last-resort node."
            ),
            "measurement": "relay_unavailable_events",
            "value": int(unavailable or 0),
        },
        {
            "id": "version_chain",
            "recommendation": (
                "The incident carried multiple versions — keep change_reason required on every escalate."
                if versions and versions > 1
                else "Single-version incident — dual-auth and versioning were not exercised here."
            ),
            "measurement": "alert_versions",
            "value": int(versions or 0),
        },
        {
            "id": "reach",
            "recommendation": (
                "Expand enrollment in units where device_delivered lag behind deliveries."
                if deliveries and reached is not None and reached < deliveries
                else "Every recorded delivery met the reached-tier floor, or no deliveries exist."
            ),
            "measurement": "deliveries_at_or_above_reached_floor",
            "value": int(reached or 0),
            "denominator": int(deliveries or 0),
        },
    ]
    return {
        "incident_id": incident_id,
        "label": incident["label"],
        "status": incident["status"],
        "recommendations": recs,
    }
