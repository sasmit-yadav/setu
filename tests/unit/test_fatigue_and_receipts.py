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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fatigue_never_suppresses_an_extreme_alert(db_conn):
    """Part 16 Day 8's DoD: "A test proves a 4th **extreme** alert is still
    delivered in full."

    F4 is [S] stretch and #2 on the written cut order, but "never suppresses"
    is the honesty-critical half of it: a fatigue feature that silently dropped
    an extreme alert would be the single worst failure this platform could have.
    apply_headline() is the only place fatigue touches an outbound message, so
    this asserts it returns the full headline and body untouched apart from the
    documented prefix — never an empty string, never a signal to skip.
    """
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    incident_id = await db_conn.fetchval(
        """
        INSERT INTO incident (label, incident_type, status, origin_source)
        VALUES ('FAT-EXTREME', 'test', 'active', 'manual')
        RETURNING id
        """
    )
    floor = await config_repo.get_int(db_conn, "fatigue.alert_count_floor")
    token = uuid.uuid4().hex[:8]
    alert_ids = []
    # floor moderate alerts, then one EXTREME as the (floor + 1)th — well past
    # the relabel threshold, which is exactly where a suppressing design breaks.
    severities = ["moderate"] * floor + ["extreme"]
    for i, severity in enumerate(severities):
        lifecycle = "active" if i == len(severities) - 1 else "superseded"
        alert_ids.append(
            await db_conn.fetchval(
                """
                INSERT INTO alert (
                    source_id, severity, headline, body, lang, area,
                    effective_at, expires_at, raw_checksum, incident_id, lifecycle_status
                )
                SELECT 'manual', $5, $3, 'EVACUATE NOW', 'en', geom,
                       now(), now() + interval '1 hour', $4, $1, $6
                FROM admin_unit WHERE id = $2
                RETURNING id
                """,
                incident_id,
                unit_id,
                f"Extreme test {i}",
                f"checksum-{token}-{i}",
                severity,
                lifecycle,
            )
        )

    extreme_id = alert_ids[-1]
    evaluation = await evaluate(db_conn, extreme_id)
    # It IS past the fatigue threshold — this is not a test of the quiet path.
    assert evaluation["relabel"] is True
    assert evaluation["related_count"] > evaluation["count_floor"]

    original = "EXTREME: dam failure imminent"
    headline, returned_eval = await apply_headline(db_conn, extreme_id, original)

    prefix = await config_repo.get(db_conn, "fatigue.relabel_prefix")
    # Delivered in full: the original headline survives verbatim inside the
    # result, and the ONLY modification is the configured prefix.
    assert original in headline, "fatigue must never truncate an extreme alert"
    assert headline == f"{prefix}{original}"
    assert headline.strip() != ""
    # And the evaluation must not carry any suppression signal at all.
    assert returned_eval["never_suppress"] is True
    assert "suppress" not in {k for k, v in returned_eval.items() if v is True} - {"never_suppress"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_apply_headline_is_idempotent_and_never_double_prefixes(db_conn):
    """A retry must not stack prefixes — 'URGENT UPDATE — URGENT UPDATE — ...'
    would look like a bug to the citizen reading it on a locked screen."""
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    incident_id = await db_conn.fetchval(
        """
        INSERT INTO incident (label, incident_type, status, origin_source)
        VALUES ('FAT-IDEMPOTENT', 'test', 'active', 'manual')
        RETURNING id
        """
    )
    floor = await config_repo.get_int(db_conn, "fatigue.alert_count_floor")
    token = uuid.uuid4().hex[:8]
    last = None
    for i in range(floor):
        # Only the newest version may be 'active' —
        # alert_one_active_per_incident_uix (F2) enforces that, and this test
        # tripped it on the first run by marking every row active.
        lifecycle = "active" if i == floor - 1 else "superseded"
        last = await db_conn.fetchval(
            """
            INSERT INTO alert (
                source_id, severity, headline, body, lang, area,
                effective_at, expires_at, raw_checksum, incident_id, lifecycle_status
            )
            SELECT 'manual', 'severe', $3, 'Body', 'en', geom,
                   now(), now() + interval '1 hour', $4, $1, $5
            FROM admin_unit WHERE id = $2
            RETURNING id
            """,
            incident_id,
            unit_id,
            f"Idem {i}",
            f"checksum-idem-{token}-{i}",
            lifecycle,
        )
    once, _ = await apply_headline(db_conn, last, "Flood warning")
    twice, _ = await apply_headline(db_conn, last, once)
    assert once == twice, "re-applying fatigue must be a no-op, not a second prefix"
