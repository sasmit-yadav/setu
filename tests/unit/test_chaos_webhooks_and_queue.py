from __future__ import annotations

import uuid

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from services.api.settings import settings
from services.delivery.assurance import record
from services.delivery.keys import keys
from services.response.assistance_queue import rebuild_from_postgres
from services.response.citizen_response import submit_response


async def _close_redis(redis: Redis) -> None:
    closer = getattr(redis, "aclose", None)
    if closer is not None:
        await closer()
        return
    await redis.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_duplicate_out_of_order_webhooks_leave_a_clean_ladder(db_conn, delivery_row):
    delivery_id = delivery_row["id"]
    sms_id = await db_conn.fetchval("SELECT id FROM channel WHERE code = 'sms'")
    await db_conn.execute(
        "UPDATE delivery SET channel_id = $1 WHERE id = $2",
        sms_id,
        delivery_id,
    )
    sequence = (
        "device_delivered",
        "provider_accepted",
        "device_delivered",
        "delivery_attempted",
        "provider_accepted",
        "device_delivered",
        "notification_opened",
        "device_delivered",
        "device_delivered",
    )
    for event in sequence:
        await record(db_conn, delivery_id, event, source="twilio_sms_webhook", evidence_id="SM-chaos")
    rows = await db_conn.fetch(
        """
        SELECT event_type FROM delivery_event
        WHERE delivery_id = $1
        ORDER BY event_type
        """,
        delivery_id,
    )
    types = [row["event_type"] for row in rows]
    assert types == ["delivery_attempted", "provider_accepted", "device_delivered"]
    level = await db_conn.fetchval("SELECT assurance_level($1)", delivery_id)
    assert level == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_assistance_queue_rebuilds_after_redis_flush(db_conn, delivery_row):
    first = await submit_response(
        db_conn,
        delivery_id=delivery_row["id"],
        response_type="trapped",
        idempotency_key=f"chaos-a-{uuid.uuid4()}",
    )
    second = await submit_response(
        db_conn,
        delivery_id=delivery_row["id"],
        response_type="medical",
        idempotency_key=f"chaos-b-{uuid.uuid4()}",
    )
    assert first["assistance_case_id"] is not None
    assert second["assistance_case_id"] is not None
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.ping()
    except (OSError, RedisError) as exc:
        await _close_redis(redis)
        pytest.skip(f"Redis unavailable: {exc}")
    try:
        await redis.delete(keys.zset_assistance())
        assert await redis.zcard(keys.zset_assistance()) == 0
        rebuilt = await rebuild_from_postgres(db_conn, redis)
        after = await redis.zrevrange(keys.zset_assistance(), 0, -1)
        assert set(after) == {str(case_id) for case_id in rebuilt}
        assert str(first["assistance_case_id"]) in after
        assert str(second["assistance_case_id"]) in after
        for case_id in (first["assistance_case_id"], second["assistance_case_id"]):
            pg_score = await db_conn.fetchval(
                "SELECT priority_score FROM assistance_case WHERE id = $1",
                case_id,
            )
            redis_score = await redis.zscore(keys.zset_assistance(), str(case_id))
            assert redis_score is not None
            assert float(redis_score) == float(pg_score)
    finally:
        await _close_redis(redis)
