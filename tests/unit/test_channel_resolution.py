"""Per-recipient channel resolution (§8.5's real-phones-vs-simulated split).

These exist because of a defect that no test caught for a long time: every
alert routed to the escalation policy's first step (fcm) for every recipient,
no seeded recipient has a push_token, and so 100% of deliveries failed with
recipient_no_push_token. The platform had never delivered anything, and D7f
reachability was 0% by construction — not because reach was genuinely zero,
but because the send always aborted before it began.

The invariant worth protecting is not "simulation happens", it is:
a recipient the platform CAN reach must not be routed to the simulator, and a
recipient it CANNOT reach must still produce a delivery that is visibly
flagged rather than a silent failure.
"""

from __future__ import annotations

import pytest

from services.targeting.escalation import (
    AREA_CHANNELS,
    CHANNEL_ADDRESS_COLUMN,
    resolve_channels_for_recipients,
)


async def _channel_code(db_conn, channel_id: int) -> str:
    return await db_conn.fetchval("SELECT code FROM channel WHERE id = $1", channel_id)


async def test_unaddressable_recipient_is_routed_to_simulator_and_flagged(
    db_conn, delivery_row
):
    """A recipient with no push_token must still get a delivery — flagged."""
    alert_id = delivery_row["alert_id"]
    recipient_id = delivery_row["recipient_id"]
    await db_conn.execute(
        "UPDATE recipient SET push_token = NULL, phone_enc = NULL WHERE id = $1",
        recipient_id,
    )
    resolved = await resolve_channels_for_recipients(db_conn, alert_id, [recipient_id])
    channel_id, simulated = resolved[recipient_id]

    assert simulated is True, "an unreachable recipient must be flagged simulated"
    assert await _channel_code(db_conn, channel_id) == "sim"


async def test_addressable_recipient_is_never_downgraded_to_the_simulator(
    db_conn, delivery_row
):
    """The important half: if we CAN reach someone for real, we must.

    A bug that simulated everything would still make the metrics move, which
    is exactly why this direction needs its own test.
    """
    alert_id = delivery_row["alert_id"]
    recipient_id = delivery_row["recipient_id"]
    await db_conn.execute(
        "UPDATE recipient SET push_token = $2 WHERE id = $1",
        recipient_id,
        "test-push-token",
    )
    resolved = await resolve_channels_for_recipients(db_conn, alert_id, [recipient_id])
    channel_id, simulated = resolved[recipient_id]

    assert simulated is False
    assert await _channel_code(db_conn, channel_id) != "sim"


async def test_phone_without_push_uses_sms_not_simulator(db_conn, delivery_row):
    """Moderate now lists SMS. A villager with a number and no app must not
    be dumped on the simulator just because FCM is step 1."""
    alert_id = delivery_row["alert_id"]
    recipient_id = delivery_row["recipient_id"]
    await db_conn.execute("UPDATE alert SET severity = 'moderate' WHERE id = $1", alert_id)
    sms_step = await db_conn.fetchval(
        """
        SELECT 1 FROM escalation_policy ep
        JOIN channel c ON c.id = ep.channel_id
        WHERE ep.severity = 'moderate' AND c.code = 'sms'
        """
    )
    if sms_step is None:
        pytest.skip("moderate SMS step not seeded")
    await db_conn.execute(
        """
        UPDATE recipient
        SET push_token = NULL, phone_enc = '\\x00'::bytea, email_enc = NULL
        WHERE id = $1
        """,
        recipient_id,
    )
    resolved = await resolve_channels_for_recipients(db_conn, alert_id, [recipient_id])
    channel_id, simulated = resolved[recipient_id]
    assert simulated is False
    assert await _channel_code(db_conn, channel_id) == "sms"


async def test_resolution_is_per_recipient_not_per_alert(db_conn, delivery_row):
    """One alert, two recipients, different reachability -> different channels.

    This is the case a single channel-per-alert choice cannot express, and it
    is the shape §8.5 describes: a few real phones alongside many simulated.
    """
    alert_id = delivery_row["alert_id"]
    reachable = delivery_row["recipient_id"]
    unit_id = await db_conn.fetchval(
        "SELECT unit_id FROM recipient WHERE id = $1", reachable
    )
    unreachable = await db_conn.fetchval(
        """
        INSERT INTO recipient (unit_id, kind, preferred_lang, consented_at)
        VALUES ($1, 'citizen', 'en', now())
        RETURNING id
        """,
        unit_id,
    )
    await db_conn.execute(
        "UPDATE recipient SET push_token = $2 WHERE id = $1", reachable, "real-token"
    )

    resolved = await resolve_channels_for_recipients(
        db_conn, alert_id, [reachable, unreachable]
    )
    assert resolved[reachable][1] is False
    assert resolved[unreachable][1] is True
    assert resolved[reachable][0] != resolved[unreachable][0]


async def test_high_reach_risk_skips_to_resilient_channel(db_conn, delivery_row):
    from services.ml.reach_risk import ensure_bootstrap_model

    alert_id = delivery_row["alert_id"]
    recipient_id = delivery_row["recipient_id"]
    unit_id = await db_conn.fetchval("SELECT unit_id FROM recipient WHERE id = $1", recipient_id)
    await db_conn.execute("UPDATE alert SET severity = 'extreme' WHERE id = $1", alert_id)
    await db_conn.execute(
        "UPDATE recipient SET phone_enc = '\\x00'::bytea, push_token = $2 WHERE id = $1",
        recipient_id,
        "unused-token",
    )
    model_id = await ensure_bootstrap_model(db_conn)
    high_risk = await db_conn.fetchval(
        "SELECT applies_if_reach_risk_gte FROM escalation_policy WHERE applies_if_reach_risk_gte IS NOT NULL LIMIT 1"
    )
    assert high_risk is not None
    await db_conn.execute(
        """
        INSERT INTO reach_prediction (alert_id, unit_id, risk_score, model_id, features)
        VALUES ($1, $2, $3, $4, '{}'::jsonb)
        ON CONFLICT (alert_id, unit_id) DO UPDATE SET risk_score = EXCLUDED.risk_score
        """,
        alert_id,
        unit_id,
        float(high_risk),
        model_id,
    )
    resolved = await resolve_channels_for_recipients(db_conn, alert_id, [recipient_id])
    channel_id, simulated = resolved[recipient_id]
    assert simulated is False
    assert await _channel_code(db_conn, channel_id) == "sms"


async def test_low_reach_risk_keeps_primary_push_channel(db_conn, delivery_row):
    from services.ml.reach_risk import ensure_bootstrap_model

    alert_id = delivery_row["alert_id"]
    recipient_id = delivery_row["recipient_id"]
    unit_id = await db_conn.fetchval("SELECT unit_id FROM recipient WHERE id = $1", recipient_id)
    await db_conn.execute("UPDATE alert SET severity = 'extreme' WHERE id = $1", alert_id)
    await db_conn.execute(
        "UPDATE recipient SET push_token = $2 WHERE id = $1",
        recipient_id,
        "real-token",
    )
    model_id = await ensure_bootstrap_model(db_conn)
    await db_conn.execute(
        """
        INSERT INTO reach_prediction (alert_id, unit_id, risk_score, model_id, features)
        VALUES ($1, $2, $3, $4, '{}'::jsonb)
        ON CONFLICT (alert_id, unit_id) DO UPDATE SET risk_score = EXCLUDED.risk_score
        """,
        alert_id,
        unit_id,
        0.0,
        model_id,
    )
    resolved = await resolve_channels_for_recipients(db_conn, alert_id, [recipient_id])
    channel_id, simulated = resolved[recipient_id]
    assert simulated is False
    assert await _channel_code(db_conn, channel_id) == "fcm"


@pytest.mark.parametrize("channel_code", sorted(CHANNEL_ADDRESS_COLUMN))
async def test_address_column_matches_a_real_recipient_column(db_conn, channel_code):
    """CHANNEL_ADDRESS_COLUMN must name columns that actually exist.

    It mirrors worker._resolve_address; if the two drift, the resolver routes
    a recipient to a channel whose send path was always going to fail.
    """
    column = CHANNEL_ADDRESS_COLUMN[channel_code]
    exists = await db_conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'recipient' AND column_name = $1
        )
        """,
        column,
    )
    assert exists, f"{channel_code} maps to recipient.{column}, which does not exist"


@pytest.mark.parametrize("channel_code", sorted(AREA_CHANNELS))
async def test_area_channels_are_real_channels(db_conn, channel_code):
    """A channel that addresses a place rather than a person still has to be a
    channel we actually have — otherwise the 'no address needed' shortcut sends
    to nothing."""
    assert await db_conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM channel WHERE code = $1)", channel_code
    ), f"AREA_CHANNELS names '{channel_code}', which is not in the channel table"
