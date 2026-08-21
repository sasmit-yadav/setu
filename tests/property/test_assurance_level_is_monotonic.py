from __future__ import annotations

import pytest

from services.delivery.assurance import record

ARRIVAL = (
    "citizen_response",
    "device_delivered",
    "delivery_attempted",
    "notification_opened",
    "provider_accepted",
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_assurance_level_is_monotonic_under_any_arrival_order(db_conn, delivery_row):
    delivery_id = delivery_row["id"]
    previous = -1
    for event in ARRIVAL:
        wrote = await record(db_conn, delivery_id, event, source="property")
        assert wrote is True
        duplicate = await record(db_conn, delivery_id, event, source="property")
        assert duplicate is False
        level = await db_conn.fetchval("SELECT assurance_level($1)", delivery_id)
        assert level >= previous
        previous = int(level)
    final = await db_conn.fetchval("SELECT assurance_level($1)", delivery_id)
    assert final == 5
    count = await db_conn.fetchval(
        "SELECT COUNT(*) FROM delivery_event WHERE delivery_id = $1",
        delivery_id,
    )
    assert count == len(ARRIVAL)
