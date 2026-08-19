from __future__ import annotations

import pytest

from services.api.db import transaction
from services.delivery.assurance import record


@pytest.mark.integration
@pytest.mark.asyncio
async def test_record_is_idempotent(db_conn, delivery_row):
    delivery_id = delivery_row["id"]
    first = await record(
        db_conn,
        delivery_id,
        "provider_accepted",
        source="test",
        evidence_id="ev-1",
    )
    second = await record(
        db_conn,
        delivery_id,
        "provider_accepted",
        source="test",
        evidence_id="ev-1",
    )
    assert first is True
    assert second is False
    count = await db_conn.fetchval(
        "SELECT COUNT(*) FROM delivery_event WHERE delivery_id = $1",
        delivery_id,
    )
    assert count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_acknowledged_event_transitions_delivery(db_conn, delivery_row):
    delivery_id = delivery_row["id"]
    async with transaction(db_conn):
        from services.delivery.state_machine import transition
        from services.delivery.states import State

        await transition(db_conn, delivery_id, State.queued)
        await transition(db_conn, delivery_id, State.sent)
        await transition(db_conn, delivery_id, State.delivered)
        await record(
            db_conn,
            delivery_id,
            "acknowledged",
            source="test_ack",
            evidence_id="ack-1",
        )
    row = await db_conn.fetchrow("SELECT state FROM delivery WHERE id = $1", delivery_id)
    assert row["state"] == "acknowledged"
