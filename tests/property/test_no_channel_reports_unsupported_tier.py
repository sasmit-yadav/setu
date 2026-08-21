from __future__ import annotations

import pytest

from services.delivery.assurance import record

TIER_TO_EVENT = {
    "provider_accept": "provider_accepted",
    "device_delivered": "device_delivered",
    "opened": "notification_opened",
    "acknowledgement": "acknowledged",
}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_channel_reports_unsupported_tier(db_conn, delivery_row):
    rows = await db_conn.fetch(
        """
        SELECT c.id AS channel_id, c.code, t.tier
        FROM channel c
        JOIN channel_capability_tier t ON t.channel_id = c.id
        WHERE t.supported = false
        """
    )
    assert rows, "channel_capability_tier must seed at least one unsupported tier"
    delivery_id = delivery_row["id"]
    for row in rows:
        event = TIER_TO_EVENT[row["tier"]]
        await db_conn.execute(
            "UPDATE delivery SET channel_id = $1 WHERE id = $2",
            row["channel_id"],
            delivery_id,
        )
        wrote = await record(db_conn, delivery_id, event, source="property")
        assert wrote is False, f"{row['code']} must not emit {event}"
        count = await db_conn.fetchval(
            """
            SELECT COUNT(*) FROM delivery_event
            WHERE delivery_id = $1 AND event_type = $2::assurance_event
            """,
            delivery_id,
            event,
        )
        assert count == 0
