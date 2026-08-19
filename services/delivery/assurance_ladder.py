from __future__ import annotations

from typing import Any

import asyncpg

TIER_TO_EVENT = {
    "provider_accept": "provider_accepted",
    "device_delivered": "device_delivered",
    "opened": "notification_opened",
    "acknowledgement": "acknowledged",
}


async def alert_assurance(conn: asyncpg.Connection, alert_id: int) -> dict[str, Any]:
    deliveries = await conn.fetch(
        """
        SELECT d.id, d.simulated, d.state, c.code AS channel_code,
               assurance_level(d.id) AS level
        FROM delivery d
        JOIN channel c ON c.id = d.channel_id
        WHERE d.alert_id = $1
        ORDER BY d.id
        """,
        alert_id,
    )
    items: list[dict[str, Any]] = []
    for delivery in deliveries:
        tiers = await conn.fetch(
            """
            SELECT tier, supported, not_applicable_reason
            FROM channel_capability_tier cct
            JOIN channel c ON c.id = cct.channel_id
            WHERE c.code = $1
            ORDER BY tier
            """,
            delivery["channel_code"],
        )
        events = await conn.fetch(
            """
            SELECT event_type, occurred_at, source, evidence_id
            FROM delivery_event
            WHERE delivery_id = $1
            ORDER BY occurred_at
            """,
            delivery["id"],
        )
        events_by_type = {row["event_type"]: row for row in events}
        rungs: list[dict[str, Any]] = []
        for tier_row in tiers:
            tier = tier_row["tier"]
            event_type = TIER_TO_EVENT[tier]
            if tier_row["supported"]:
                event = events_by_type.get(event_type)
                if event:
                    status = "recorded"
                    rungs.append(
                        {
                            "tier": tier,
                            "status": status,
                            "event_type": event_type,
                            "occurred_at": event["occurred_at"].isoformat(),
                            "source": event["source"],
                            "evidence_id": event["evidence_id"],
                        }
                    )
                else:
                    rungs.append(
                        {
                            "tier": tier,
                            "status": "pending",
                            "event_type": event_type,
                        }
                    )
            else:
                rungs.append(
                    {
                        "tier": tier,
                        "status": "not_applicable",
                        "event_type": event_type,
                        "reason": tier_row["not_applicable_reason"],
                    }
                )
        items.append(
            {
                "delivery_id": delivery["id"],
                "channel_code": delivery["channel_code"],
                "simulated": delivery["simulated"],
                "state": delivery["state"],
                "assurance_level": int(delivery["level"]),
                "rungs": rungs,
            }
        )
    return {"alert_id": alert_id, "deliveries": items}
