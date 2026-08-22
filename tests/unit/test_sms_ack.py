"""Inbound SAFE / HELP must write the same citizen_response as the PWA buttons."""

from __future__ import annotations

import uuid

import pytest
from redis.asyncio import Redis

from services.api import config_repo
from services.api.settings import settings
from services.enrollment.phone_hash import phone_hash
from services.enrollment.sms_keyword import handle_inbound


async def _upsert(conn, key: str, value: str) -> None:
    await conn.execute(
        """
        INSERT INTO app_config (key, value, unit, note)
        VALUES ($1, $2, 'string', 'test')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """,
        key,
        value,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sms_safe_and_help_write_responses(db_conn):
    if not settings.phone_hash_pepper:
        pytest.skip("PHONE_HASH_PEPPER missing")
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit WHERE geom IS NOT NULL LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")

    await _upsert(db_conn, "response.sms_keyword.safe", "SAFE")
    await _upsert(db_conn, "response.sms_keyword.help", "HELP")
    await _upsert(db_conn, "response.sms_reply.safe", "SETU: marked safe")
    await _upsert(db_conn, "response.sms_reply.help", "SETU: help received")
    await _upsert(db_conn, "response.sms_reply.hint", "SETU: Reply SAFE or HELP.")

    phone = f"+9198{uuid.uuid4().int % 100000000:08d}"
    digest = phone_hash(phone)
    recipient_id = await db_conn.fetchval(
        """
        INSERT INTO recipient (unit_id, kind, phone_hash, consented_at, consent_source)
        VALUES ($1, 'citizen', $2, now(), 'test_sms_ack')
        RETURNING id
        """,
        unit_id,
        digest,
    )
    incident_id = await db_conn.fetchval(
        """
        INSERT INTO incident (label, incident_type, status, origin_source)
        VALUES ($1, 'test', 'active', 'manual')
        RETURNING id
        """,
        f"SMSACK-{uuid.uuid4().hex[:6]}",
    )
    alert_id = await db_conn.fetchval(
        """
        INSERT INTO alert (
            source_id, severity, headline, body, lang, area,
            effective_at, expires_at, raw_checksum, incident_id, lifecycle_status
        )
        SELECT 'manual', 'moderate', 'Ack test', 'Body', 'en', geom,
               now(), now() + interval '2 hours', $1, $2, 'active'
        FROM admin_unit WHERE id = $3
        RETURNING id
        """,
        f"ack-{uuid.uuid4().hex}",
        incident_id,
        unit_id,
    )
    channel_id = await db_conn.fetchval("SELECT id FROM channel WHERE code = 'sms'")
    delivery_id = await db_conn.fetchval(
        """
        INSERT INTO delivery (alert_id, recipient_id, channel_id, state)
        VALUES ($1, $2, $3, 'sent')
        RETURNING id
        """,
        alert_id,
        recipient_id,
        channel_id,
    )

    redis = Redis.from_url(settings.redis_url)
    try:
        safe_kw = await config_repo.get_str(db_conn, "response.sms_keyword.safe")
        result = await handle_inbound(db_conn, redis, from_number=phone, body=f"{safe_kw} now")
        assert result.action == "safe"
        assert "safe" in result.reply_text.lower()
        kind = await db_conn.fetchval(
            "SELECT response_type FROM citizen_response WHERE delivery_id = $1",
            delivery_id,
        )
        assert kind == "safe"

        help_kw = await config_repo.get_str(db_conn, "response.sms_keyword.help")
        # New delivery so HELP is not blocked by the SAFE row / idempotency.
        help_delivery = await db_conn.fetchval(
            """
            INSERT INTO delivery (alert_id, recipient_id, channel_id, state, attempt)
            VALUES ($1, $2, $3, 'sent', 2)
            RETURNING id
            """,
            alert_id,
            recipient_id,
            channel_id,
        )
        # Latest delivery wins.
        helped = await handle_inbound(db_conn, redis, from_number=phone, body=help_kw)
        assert helped.action == "help"
        help_kind = await db_conn.fetchval(
            "SELECT response_type FROM citizen_response WHERE delivery_id = $1",
            help_delivery,
        )
        assert help_kind == "other"

        unknown = await handle_inbound(db_conn, redis, from_number=phone, body="PING")
        assert unknown.action == "unknown"
        assert unknown.reply_text
    finally:
        await redis.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sms_safe_without_live_alert_says_so(db_conn):
    if not settings.phone_hash_pepper:
        pytest.skip("PHONE_HASH_PEPPER missing")
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    await _upsert(db_conn, "response.sms_keyword.safe", "SAFE")
    await _upsert(db_conn, "response.sms_reply.no_alert", "SETU: no live warning")
    phone = f"+9197{uuid.uuid4().int % 100000000:08d}"
    await db_conn.execute(
        """
        INSERT INTO recipient (unit_id, kind, phone_hash, consented_at, consent_source)
        VALUES ($1, 'citizen', $2, now(), 'test_sms_ack')
        """,
        unit_id,
        phone_hash(phone),
    )
    redis = Redis.from_url(settings.redis_url)
    try:
        result = await handle_inbound(db_conn, redis, from_number=phone, body="SAFE")
        assert result.action == "no_alert"
    finally:
        await redis.aclose()
