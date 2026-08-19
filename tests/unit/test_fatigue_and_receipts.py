from __future__ import annotations

import uuid

import pytest
from redis.asyncio import Redis

from services.api import config_repo
from services.api.settings import settings
from services.delivery.fatigue import apply_headline, evaluate
from services.delivery.receipts import consume_nonce, record_receipt, store_nonce


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fatigue_relabels_after_threshold(db_conn):
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    incident_id = await db_conn.fetchval(
        """
        INSERT INTO incident (label, incident_type, status, origin_source)
        VALUES ('FAT-INC', 'test', 'active', 'manual')
        RETURNING id
        """
    )
    floor = await config_repo.get_int(db_conn, "fatigue.alert_count_floor")
    alert_ids = []
    for i in range(floor):
        lifecycle = "active" if i == floor - 1 else "superseded"
        alert_id = await db_conn.fetchval(
            """
            INSERT INTO alert (
                source_id, severity, headline, body, lang, area,
                effective_at, expires_at, raw_checksum, incident_id, lifecycle_status
            )
            SELECT 'manual', 'moderate', $3, 'Body', 'en', geom,
                   now(), now() + interval '1 hour', $4, $1, $5
            FROM admin_unit WHERE id = $2
            RETURNING id
            """,
            incident_id,
            unit_id,
            f"Headline {i}",
            f"checksum-{i}",
            lifecycle,
        )
        alert_ids.append(alert_id)
    evaluation = await evaluate(db_conn, alert_ids[-1])
    assert evaluation["relabel"] is True
    headline, _ = await apply_headline(db_conn, alert_ids[-1], "Latest warning")
    prefix = await config_repo.get(db_conn, "fatigue.relabel_prefix")
    assert headline.startswith(prefix)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_receipt_nonce_rejected_when_invalid(db_conn, delivery_row):
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        assert not await consume_nonce(redis, delivery_row["id"], "wrong-nonce")
        nonce = str(uuid.uuid4())
        await store_nonce(redis, db_conn, delivery_row["id"], nonce)
        assert await consume_nonce(redis, delivery_row["id"], nonce)
        recorded = await record_receipt(
            db_conn,
            delivery_row["id"],
            event_type="device_delivered",
            nonce=nonce,
        )
        assert recorded
    finally:
        await redis.close()
