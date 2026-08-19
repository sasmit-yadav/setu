from __future__ import annotations

import pytest

from services.api.db import transaction
from services.delivery.state_machine import transition
from services.delivery.states import IllegalTransition, State


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pending_to_queued_sets_timestamp(db_conn, delivery_row):
    delivery_id = delivery_row["id"]
    async with transaction(db_conn):
        await transition(db_conn, delivery_id, State.queued)
    row = await db_conn.fetchrow("SELECT state, queued_at FROM delivery WHERE id = $1", delivery_id)
    assert row["state"] == "queued"
    assert row["queued_at"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_happy_path_to_acknowledged(db_conn, delivery_row):
    delivery_id = delivery_row["id"]
    async with transaction(db_conn):
        await transition(db_conn, delivery_id, State.queued)
        await transition(db_conn, delivery_id, State.sent)
        await transition(db_conn, delivery_id, State.delivered)
        await transition(db_conn, delivery_id, State.acknowledged)
    row = await db_conn.fetchrow(
        "SELECT state, acked_at FROM delivery WHERE id = $1",
        delivery_id,
    )
    assert row["state"] == "acknowledged"
    assert row["acked_at"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_illegal_transition_raises(db_conn, delivery_row):
    delivery_id = delivery_row["id"]
    with pytest.raises(IllegalTransition):
        async with transaction(db_conn):
            await transition(db_conn, delivery_id, State.sent)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_failed_can_retry_to_pending(db_conn, delivery_row):
    delivery_id = delivery_row["id"]
    async with transaction(db_conn):
        await transition(db_conn, delivery_id, State.queued)
        await transition(db_conn, delivery_id, State.failed)
        await transition(db_conn, delivery_id, State.pending)
    row = await db_conn.fetchrow("SELECT state FROM delivery WHERE id = $1", delivery_id)
    assert row["state"] == "pending"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_event_written(db_conn, delivery_row):
    delivery_id = delivery_row["id"]
    async with transaction(db_conn):
        await transition(db_conn, delivery_id, State.queued)
    count = await db_conn.fetchval(
        "SELECT COUNT(*) FROM audit_event WHERE delivery_id = $1",
        delivery_id,
    )
    assert count >= 1
