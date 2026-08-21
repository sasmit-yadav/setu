"""B3 — retry backoff and channel escalation actually driven by the policy table.

Before this existed, `escalation_policy.wait_before_next_s`,
`backoff_multiplier`, `jitter_ms` and `max_attempts` were seeded per severity
and read by nothing: every delivery in the database was `attempt = 1`, the
`escalated` state had zero rows, and 462 failures were abandoned after one try
on one channel. Part 19 requires "retry backoff shows visible growth + jitter
in a captured log from a forced-failure test", which was unsatisfiable.

The growth-and-jitter tests below are the pure-function half (Part 24's whole
point — a flat wait treats a one-second outage like a ten-minute one). The
escalation tests are the chain half, including the ordering guarantee that
matters most for B9: a human is spent only once every digital step is spent.
"""

from __future__ import annotations

import random
import uuid

import pytest
from redis.asyncio import Redis

from services.api.settings import settings
from services.delivery.retry import (
    compute_delay_s,
    due_delivery_ids,
    handle_failure,
    schedule_retry,
)


# ── growth and jitter: pure, no database ────────────────────────────────────

def test_backoff_grows_geometrically_without_jitter():
    delays = [
        compute_delay_s(a, wait_before_next_s=60, backoff_multiplier=1.5, jitter_ms=0)
        for a in (1, 2, 3, 4)
    ]
    assert delays == [60.0, 90.0, 135.0, 202.5]
    # Strictly increasing is the property Part 24 asks for by name.
    assert all(b > a for a, b in zip(delays, delays[1:]))


def test_backoff_multiplier_of_one_is_flat_by_design():
    """A multiplier of 1.0 is a legitimate policy choice (the siren and relay
    steps use it), and must stay flat rather than accidentally growing."""
    delays = [
        compute_delay_s(a, wait_before_next_s=45, backoff_multiplier=1.0, jitter_ms=0)
        for a in (1, 2, 3)
    ]
    assert delays == [45.0, 45.0, 45.0]


def test_jitter_varies_the_delay_and_stays_within_the_window():
    rng = random.Random(1234)
    samples = [
        compute_delay_s(
            1, wait_before_next_s=60, backoff_multiplier=1.5, jitter_ms=5000, rng=rng
        )
        for _ in range(200)
    ]
    assert len(set(samples)) > 1, "jitter produced identical delays — no jitter at all"
    # +/- half the 5000ms window around the 60s base.
    assert all(57.5 <= s <= 62.5 for s in samples), (min(samples), max(samples))
    # Symmetric, so the mean stays on the policy curve rather than drifting past it.
    assert abs(sum(samples) / len(samples) - 60.0) < 0.5


def test_jitter_never_produces_a_negative_delay():
    rng = random.Random(7)
    samples = [
        compute_delay_s(
            1, wait_before_next_s=0, backoff_multiplier=1.0, jitter_ms=4000, rng=rng
        )
        for _ in range(200)
    ]
    assert min(samples) >= 0.0


def test_attempt_is_one_based():
    with pytest.raises(ValueError):
        compute_delay_s(0, wait_before_next_s=10, backoff_multiplier=2.0, jitter_ms=0)


# ── the due-time queue ──────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_due_queue_returns_only_elapsed_entries():
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        from services.delivery.keys import keys

        await redis.delete(keys.zset_retry())
        now = 1_000_000.0
        await schedule_retry(redis, 111, 0.0, now=now)      # due
        await schedule_retry(redis, 222, 30.0, now=now)     # not yet
        due = await due_delivery_ids(redis, now=now + 1)
        assert due == [111]
        # The not-yet entry must still be queued, not consumed.
        assert await redis.zscore(keys.zset_retry(), "222") is not None
        later = await due_delivery_ids(redis, now=now + 60)
        assert later == [222]
    finally:
        await redis.delete("setu:v1:zset:retry")
        await redis.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_claimed_retry_is_not_handed_to_a_second_worker():
    """Two workers draining concurrently must not both send to the same person."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        from services.delivery.keys import keys

        await redis.delete(keys.zset_retry())
        await schedule_retry(redis, 999, 0.0, now=0.0)
        first = await due_delivery_ids(redis, now=1.0)
        second = await due_delivery_ids(redis, now=1.0)
        assert first == [999]
        assert second == [], "the same delivery was claimed twice"
    finally:
        await redis.delete("setu:v1:zset:retry")
        await redis.aclose()


# ── the chain, against the real policy table ────────────────────────────────

async def _delivery_on(db_conn, channel_code: str, severity: str = "extreme"):
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    incident_id = await db_conn.fetchval(
        """
        INSERT INTO incident (label, incident_type, status, origin_source)
        VALUES ($1, 'test', 'active', 'manual') RETURNING id
        """,
        f"RETRY-{uuid.uuid4().hex[:6]}",
    )
    alert_id = await db_conn.fetchval(
        """
        INSERT INTO alert (
            source_id, severity, headline, body, lang, area,
            effective_at, expires_at, raw_checksum, incident_id, lifecycle_status
        )
        SELECT 'manual', $1, 'Retry chain', 'Body', 'en', geom,
               now(), now() + interval '2 hours', $2, $3, 'active'
        FROM admin_unit WHERE id = $4
        RETURNING id
        """,
        severity,
        f"checksum-retry-{uuid.uuid4().hex[:10]}",
        incident_id,
        unit_id,
    )
    recipient_id = await db_conn.fetchval(
        """
        INSERT INTO recipient (unit_id, kind, consented_at, consent_source)
        VALUES ($1, 'citizen', now(), 'test_retry') RETURNING id
        """,
        unit_id,
    )
    channel_id = await db_conn.fetchval(
        "SELECT id FROM channel WHERE code = $1", channel_code
    )
    delivery_id = await db_conn.fetchval(
        """
        INSERT INTO delivery (alert_id, recipient_id, channel_id, state, attempt)
        VALUES ($1, $2, $3, 'failed', 1) RETURNING id
        """,
        alert_id,
        recipient_id,
        channel_id,
    )
    return alert_id, recipient_id, int(delivery_id), int(channel_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_first_failure_retries_the_same_channel(db_conn):
    """extreme/fcm is seeded max_attempts=2, so attempt 1 must retry, not escalate."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        _, _, delivery_id, channel_id = await _delivery_on(db_conn, "fcm")
        out = await handle_failure(db_conn, redis, delivery_id, reason="forced")
        assert out["decision"] == "retry", out
        assert out["attempt"] == 2
        assert out["delay_s"] > 0
        row = await db_conn.fetchrow(
            "SELECT state, attempt, channel_id FROM delivery WHERE id = $1", delivery_id
        )
        assert row["state"] == "pending"
        assert row["attempt"] == 2
        assert row["channel_id"] == channel_id, "retry must stay on the same channel"
    finally:
        await redis.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_exhausting_a_channel_escalates_to_the_next_policy_step(db_conn):
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        _, _, delivery_id, fcm_id = await _delivery_on(db_conn, "fcm")
        # Spend the channel: extreme/fcm allows 2 attempts.
        await db_conn.execute("UPDATE delivery SET attempt = 2 WHERE id = $1", delivery_id)
        out = await handle_failure(db_conn, redis, delivery_id, reason="forced")
        assert out["decision"] == "escalated", out
        assert out["to_channel_id"] != fcm_id

        # The spent delivery is `escalated`, not `failed` — the recipient was
        # handed to another channel, not abandoned.
        assert await db_conn.fetchval(
            "SELECT state FROM delivery WHERE id = $1", delivery_id
        ) == "escalated"

        new_row = await db_conn.fetchrow(
            "SELECT state, attempt, channel_id FROM delivery WHERE id = $1",
            out["new_delivery_id"],
        )
        assert new_row["state"] == "pending"
        assert new_row["attempt"] == 1, "a new channel starts its own attempt budget"

        code = await db_conn.fetchval(
            "SELECT code FROM channel WHERE id = $1", new_row["channel_id"]
        )
        assert code == "sms", f"extreme step after fcm should be sms, got {code}"
    finally:
        await redis.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_escalation_is_audited_with_both_channels(db_conn):
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        alert_id, _, delivery_id, _ = await _delivery_on(db_conn, "fcm")
        await db_conn.execute("UPDATE delivery SET attempt = 2 WHERE id = $1", delivery_id)
        await handle_failure(db_conn, redis, delivery_id, reason="forced")
        # delivery.channel_escalated, not delivery.escalated — the latter is the
        # state machine's own transition event. Both should exist: the state
        # change and the reason for it.
        row = await db_conn.fetchrow(
            """
            SELECT payload FROM audit_event
            WHERE alert_id = $1 AND event_type = 'delivery.channel_escalated'
            """,
            alert_id,
        )
        assert row is not None, "escalation left no ledger entry"
        body = str(row["payload"])
        assert "from_channel_id" in body and "to_channel_id" in body

        state_change = await db_conn.fetchval(
            """
            SELECT COUNT(*) FROM audit_event
            WHERE alert_id = $1 AND event_type = 'delivery.escalated'
            """,
            alert_id,
        )
        assert state_change >= 1, "the state transition itself was not audited"
    finally:
        await redis.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_last_step_in_the_chain_reports_exhausted_not_escalated(db_conn):
    """The end of the chain is what may legitimately spend a human (B9). It must
    be reachable only here — never on the first failure."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        last_code = await db_conn.fetchval(
            """
            SELECT c.code FROM escalation_policy p
            JOIN channel c ON c.id = p.channel_id
            WHERE p.severity = 'extreme'
            ORDER BY p.step_order DESC LIMIT 1
            """
        )
        _, _, delivery_id, _ = await _delivery_on(db_conn, last_code)
        max_attempts = await db_conn.fetchval(
            """
            SELECT p.max_attempts FROM escalation_policy p
            JOIN channel c ON c.id = p.channel_id
            WHERE p.severity = 'extreme' AND c.code = $1
            """,
            last_code,
        )
        await db_conn.execute(
            "UPDATE delivery SET attempt = $2 WHERE id = $1", delivery_id, int(max_attempts)
        )
        out = await handle_failure(db_conn, redis, delivery_id, reason="forced")
        assert out["decision"] == "chain_exhausted", out
    finally:
        await redis.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simulated_carrier_has_no_policy_and_is_not_retried(db_conn):
    """`sim` is a fallback, not a policy step. Retrying it would mean inventing a
    schedule the policy table never specified — a hardcoded timing by the back
    door."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        _, _, delivery_id, _ = await _delivery_on(db_conn, "sim")
        out = await handle_failure(db_conn, redis, delivery_id, reason="forced")
        assert out["decision"] == "no_policy_for_channel", out
    finally:
        await redis.aclose()


# ── the worker's side: failure hook and the drain ───────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_after_failure_retries_without_spending_a_human(db_conn):
    """B9's cost discipline. `_after_failure` must only reach for a human when
    the chain is exhausted — a human's time is the most expensive channel in
    the table (cost_weight 12), and it used to be spent on the FIRST failure."""
    from services.delivery.worker import _after_failure

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        alert_id, recipient_id, delivery_id, _ = await _delivery_on(db_conn, "fcm")
        human_id = await db_conn.fetchval("SELECT id FROM channel WHERE code = 'human_relay'")

        out = await _after_failure(
            db_conn, redis, delivery_id,
            alert_id=alert_id, recipient_id=recipient_id, reason="forced",
        )
        assert out["decision"] == "retry"
        relay_rows = await db_conn.fetchval(
            "SELECT COUNT(*) FROM delivery WHERE alert_id = $1 AND channel_id = $2",
            alert_id, human_id,
        )
        assert relay_rows == 0, "a human was queued on the first failure"
    finally:
        await redis.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_after_failure_reaches_the_human_only_when_the_chain_is_spent(db_conn):
    from services.delivery.worker import _after_failure

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        last_code = await db_conn.fetchval(
            """
            SELECT c.code FROM escalation_policy p
            JOIN channel c ON c.id = p.channel_id
            WHERE p.severity = 'extreme' ORDER BY p.step_order DESC LIMIT 1
            """
        )
        alert_id, recipient_id, delivery_id, _ = await _delivery_on(db_conn, last_code)
        max_attempts = await db_conn.fetchval(
            """
            SELECT p.max_attempts FROM escalation_policy p
            JOIN channel c ON c.id = p.channel_id
            WHERE p.severity = 'extreme' AND c.code = $1
            """,
            last_code,
        )
        await db_conn.execute(
            "UPDATE delivery SET attempt = $2 WHERE id = $1", delivery_id, int(max_attempts)
        )
        out = await _after_failure(
            db_conn, redis, delivery_id,
            alert_id=alert_id, recipient_id=recipient_id, reason="forced",
        )
        assert out["decision"] == "chain_exhausted"
    finally:
        await redis.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_drain_due_retries_sends_only_elapsed_deliveries(db_conn):
    """A scheduled retry must actually be picked up, and one that is not yet due
    must be left alone — otherwise backoff is decorative."""
    from services.delivery.channels.registry import load_channel_adapters
    from services.delivery.keys import keys
    from services.delivery.worker import drain_due_retries

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.delete(keys.zset_retry())
        _, _, due_id, _ = await _delivery_on(db_conn, "fcm")
        _, _, later_id, _ = await _delivery_on(db_conn, "fcm")
        await db_conn.execute(
            "UPDATE delivery SET state = 'pending' WHERE id = ANY($1::bigint[])",
            [due_id, later_id],
        )
        # One already due, one far in the future.
        await schedule_retry(redis, due_id, -5.0)
        await schedule_retry(redis, later_id, 3600.0)

        adapters = await load_channel_adapters(db_conn)
        ran = await drain_due_retries(db_conn, redis, adapters)
        assert ran == 1, f"expected exactly the due delivery, ran {ran}"
        # The future one is still queued.
        assert await redis.zscore(keys.zset_retry(), str(later_id)) is not None
    finally:
        await redis.delete("setu:v1:zset:retry")
        await redis.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_drain_skips_a_vanished_delivery(db_conn):
    """A queued id whose row is gone must not crash the drain — the retry set
    outlives individual rows (a superseded alert's deliveries get expired)."""
    from services.delivery.channels.registry import load_channel_adapters
    from services.delivery.keys import keys
    from services.delivery.worker import drain_due_retries

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.delete(keys.zset_retry())
        await schedule_retry(redis, 2_000_000_000, -1.0)  # no such delivery
        adapters = await load_channel_adapters(db_conn)
        ran = await drain_due_retries(db_conn, redis, adapters)
        assert ran == 1  # claimed, then skipped without raising
    finally:
        await redis.delete("setu:v1:zset:retry")
        await redis.aclose()
