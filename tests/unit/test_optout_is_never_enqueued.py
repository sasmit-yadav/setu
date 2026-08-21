"""Withdrawn consent must be honoured by the targeting query, not just recorded.

Part 19's binding list: "`STOP` sets `opted_out_at` and that recipient is
**never enqueued again**." The exclusion exists — `recipients_in_area()` filters
on `r.opted_out_at IS NULL` — but nothing tested it in either direction, so
dropping that one WHERE clause during a refactor would silently start
re-messaging people who explicitly opted out, and every test would still pass.

For a platform whose consent is structural (§2.7) that is the worst class of
regression available: it is not a wrong number on a dashboard, it is contacting
someone who asked not to be contacted. So this asserts the whole path —
the STOP keyword writes the timestamp, the audit ledger records it, and the
targeting query stops returning that recipient.
"""

from __future__ import annotations

import uuid

import pytest
from redis.asyncio import Redis

from services.api import config_repo
from services.api.settings import settings
from services.enrollment.phone_hash import phone_hash
from services.enrollment.sms_keyword import handle_inbound
from services.targeting.geo import recipients_in_area, target_count


async def _unit_with_geom(conn) -> int:
    unit_id = await conn.fetchval("SELECT id FROM admin_unit WHERE geom IS NOT NULL LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    return int(unit_id)


async def _alert_covering(conn, unit_id: int) -> int:
    incident_id = await conn.fetchval(
        """
        INSERT INTO incident (label, incident_type, status, origin_source)
        VALUES ($1, 'test', 'active', 'manual')
        RETURNING id
        """,
        f"OPTOUT-{uuid.uuid4().hex[:6]}",
    )
    return await conn.fetchval(
        """
        INSERT INTO alert (
            source_id, severity, headline, body, lang, area,
            effective_at, expires_at, raw_checksum, incident_id, lifecycle_status
        )
        SELECT 'manual', 'severe', 'Opt-out targeting', 'Body', 'en', geom,
               now(), now() + interval '2 hours', $1, $2, 'draft'
        FROM admin_unit WHERE id = $3
        RETURNING id
        """,
        f"checksum-optout-{uuid.uuid4().hex[:10]}",
        incident_id,
        unit_id,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_opted_out_recipient_is_excluded_from_targeting(db_conn):
    unit_id = await _unit_with_geom(db_conn)
    alert_id = await _alert_covering(db_conn, unit_id)

    recipient_id = await db_conn.fetchval(
        """
        INSERT INTO recipient (unit_id, kind, consented_at, consent_source)
        VALUES ($1, 'citizen', now(), 'test_optout')
        RETURNING id
        """,
        unit_id,
    )
    try:
        # Consented: must be targeted.
        assert recipient_id in await recipients_in_area(db_conn, alert_id)
        before = await target_count(db_conn, alert_id)

        # Withdraw consent.
        await db_conn.execute(
            "UPDATE recipient SET opted_out_at = now() WHERE id = $1", recipient_id
        )

        after_ids = await recipients_in_area(db_conn, alert_id)
        assert recipient_id not in after_ids, (
            "an opted-out recipient was still returned by the targeting query — "
            "STOP would be recorded but not honoured"
        )
        assert await target_count(db_conn, alert_id) == before - 1
    finally:
        await db_conn.execute("DELETE FROM recipient WHERE id = $1", recipient_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unconsented_recipient_is_also_excluded(db_conn):
    """The other half of the same WHERE clause. A row with no `consented_at` has
    never opted in, which is not the same state as having opted out, but both
    must be excluded."""
    unit_id = await _unit_with_geom(db_conn)
    alert_id = await _alert_covering(db_conn, unit_id)

    recipient_id = await db_conn.fetchval(
        """
        INSERT INTO recipient (unit_id, kind, consented_at, consent_source)
        VALUES ($1, 'citizen', NULL, 'test_optout')
        RETURNING id
        """,
        unit_id,
    )
    try:
        assert recipient_id not in await recipients_in_area(db_conn, alert_id)
    finally:
        await db_conn.execute("DELETE FROM recipient WHERE id = $1", recipient_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stop_keyword_sets_opted_out_and_audits_it(db_conn):
    """End of the path: the inbound STOP handler itself, not a hand-written
    UPDATE. Uses the configured keyword rather than the literal 'STOP', because
    the keyword is an app_config row (Rule 1)."""
    unit_id = await _unit_with_geom(db_conn)
    phone = f"+9198{uuid.uuid4().int % 100000000:08d}"
    digest = phone_hash(phone)

    recipient_id = await db_conn.fetchval(
        """
        INSERT INTO recipient (unit_id, kind, phone_hash, consented_at, consent_source)
        VALUES ($1, 'citizen', $2, now(), 'test_optout')
        RETURNING id
        """,
        unit_id,
        digest,
    )
    redis = Redis.from_url(settings.redis_url)
    try:
        stop_kw = await config_repo.get_str(db_conn, "enrollment.sms_keyword_stop")
        result = await handle_inbound(db_conn, redis, from_number=phone, body=stop_kw)
        assert result.action == "stop"
        assert result.reply_text, "STOP must send an auto-reply confirming the opt-out"

        opted_out_at = await db_conn.fetchval(
            "SELECT opted_out_at FROM recipient WHERE id = $1", recipient_id
        )
        assert opted_out_at is not None, "STOP did not set opted_out_at"

        audited = await db_conn.fetchval(
            """
            SELECT COUNT(*) FROM audit_event
            WHERE event_type = 'enrollment.sms_stop'
              AND payload::text LIKE '%' || $1::text || '%'
            """,
            str(recipient_id),
        )
        assert audited >= 1, "an opt-out left no ledger entry"
    finally:
        await db_conn.execute("DELETE FROM recipient WHERE id = $1", recipient_id)
        await redis.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stop_then_alert_does_not_enqueue_that_recipient(db_conn):
    """The Part 19 sentence in one test: STOP, then dispatch-time targeting for a
    fresh alert covering their unit must not include them."""
    unit_id = await _unit_with_geom(db_conn)
    phone = f"+9197{uuid.uuid4().int % 100000000:08d}"
    digest = phone_hash(phone)
    recipient_id = await db_conn.fetchval(
        """
        INSERT INTO recipient (unit_id, kind, phone_hash, consented_at, consent_source)
        VALUES ($1, 'citizen', $2, now(), 'test_optout')
        RETURNING id
        """,
        unit_id,
        digest,
    )
    redis = Redis.from_url(settings.redis_url)
    try:
        first_alert = await _alert_covering(db_conn, unit_id)
        assert recipient_id in await recipients_in_area(db_conn, first_alert)

        stop_kw = await config_repo.get_str(db_conn, "enrollment.sms_keyword_stop")
        await handle_inbound(db_conn, redis, from_number=phone, body=stop_kw)

        # A brand-new alert, after the opt-out.
        later_alert = await _alert_covering(db_conn, unit_id)
        assert recipient_id not in await recipients_in_area(db_conn, later_alert), (
            "recipient was enqueued for a new alert after sending STOP"
        )
    finally:
        await db_conn.execute("DELETE FROM recipient WHERE id = $1", recipient_id)
        await redis.aclose()
