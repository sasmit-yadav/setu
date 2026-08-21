from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import asyncpg

from services.api import config_repo

# Which recipient column carries a usable address for each channel. This is the
# same mapping services/delivery/worker.py::_resolve_address enforces at send
# time — kept here so the channel DECISION and the address RESOLUTION cannot
# drift apart and produce a delivery that was always going to fail.
CHANNEL_ADDRESS_COLUMN = {
    "fcm": "push_token",
    "sms": "phone_enc",
    "ivr": "phone_enc",
    "human_relay": "phone_enc",
    "email": "email_enc",
}
# Channels that address a PLACE, not a person (§12.3's "non-addressed area
# broadcast"). A siren needs no recipient address, so a recipient is always
# "addressable" on it.
AREA_CHANNELS = frozenset({"siren", "community_relay"})


def _channel_from_steps(steps: Sequence[Any], score: float) -> int:
    if not steps:
        raise ValueError("no escalation policy steps")
    for step in steps:
        threshold = step["applies_if_reach_risk_gte"]
        if threshold is None or score >= float(threshold):
            return int(step["channel_id"])
    return int(steps[0]["channel_id"])


async def _policy_steps(conn: asyncpg.Connection, severity: str) -> list[Any]:
    steps = await conn.fetch(
        """
        SELECT channel_id, applies_if_reach_risk_gte
        FROM escalation_policy
        WHERE severity = $1
        ORDER BY step_order ASC
        """,
        severity,
    )
    if not steps:
        raise ValueError(f"no escalation policy for severity {severity}")
    return list(steps)


async def primary_channel_for_alert(conn: asyncpg.Connection, alert_id: int) -> int:
    severity = await conn.fetchval("SELECT severity FROM alert WHERE id = $1", alert_id)
    if severity is None:
        raise ValueError("alert not found")
    return await initial_channel_for(conn, alert_id=alert_id, unit_id=None, severity=str(severity))


async def initial_channel_for(
    conn: asyncpg.Connection,
    *,
    alert_id: int,
    unit_id: int | None,
    severity: str,
    risk_score: float | None = None,
) -> int:
    score = risk_score
    if score is None and unit_id is not None:
        stored = await conn.fetchval(
            """
            SELECT risk_score FROM reach_prediction
            WHERE alert_id = $1 AND unit_id = $2
            """,
            alert_id,
            unit_id,
        )
        score = float(stored) if stored is not None else 0.0
    elif score is None:
        score = 0.0
    steps = await _policy_steps(conn, severity)
    return _channel_from_steps(steps, score)


async def resolve_channels_for_recipients(
    conn: asyncpg.Connection, alert_id: int, recipient_ids: list[int]
) -> dict[int, tuple[int, bool]]:
    """Decide, PER RECIPIENT, which channel to use and whether it is simulated.

    Returns {recipient_id: (channel_id, simulated)}.

    WHY PER RECIPIENT: the platform's own pitch (§8.5) is that a handful of
    recipients are wired to real phones and "the other 337 run the identical
    delivery engine, state machine and escalation logic against a simulated
    carrier". A single channel chosen for the whole alert cannot express that.

    Before this existed, every alert routed to the policy's first step (fcm)
    for everyone, and since no seeded recipient has a push_token, 100% of
    deliveries failed with recipient_no_push_token. A disaster-alert delivery
    platform in which no alert has ever been delivered cannot demonstrate the
    assurance ladder, and D7f reachability is 0% by construction — not because
    reach is genuinely zero, but because the send always aborted.

    HONESTY (Trap 5, §8.5): falling back to the simulated carrier NEVER hides
    anything. delivery.simulated is set true, the SIM badge renders from it,
    and channel_capability_tier already records that sim's evidence comes from
    a 'simulated_carrier_profile'. The alternative — leaving the delivery to
    fail — is not more honest, it just produces a system that does nothing.
    """
    if not recipient_ids:
        return {}

    severity = await conn.fetchval("SELECT severity FROM alert WHERE id = $1", alert_id)
    if severity is None:
        raise ValueError("alert not found")
    rec_rows = await conn.fetch(
        """
        SELECT id, unit_id FROM recipient WHERE id = ANY($1::bigint[])
        """,
        recipient_ids,
    )
    units = {int(row["id"]): int(row["unit_id"]) for row in rec_rows}
    unit_ids = list(set(units.values()))
    pred_rows = await conn.fetch(
        """
        SELECT unit_id, risk_score
        FROM reach_prediction
        WHERE alert_id = $1 AND unit_id = ANY($2::bigint[])
        """,
        alert_id,
        unit_ids,
    )
    risks = {int(row["unit_id"]): float(row["risk_score"]) for row in pred_rows}
    sim_id = await conn.fetchval("SELECT id FROM channel WHERE code = 'sim'")
    simulate_fallback = await config_repo.get_bool(
        conn, "delivery.simulate_when_unaddressable"
    )
    channel_codes = {
        int(row["id"]): str(row["code"])
        for row in await conn.fetch("SELECT id, code FROM channel")
    }
    steps = await _policy_steps(conn, str(severity))

    address_flags: dict[str, dict[int, bool]] = {}
    for column in set(CHANNEL_ADDRESS_COLUMN.values()):
        rows = await conn.fetch(
            f"""
            SELECT id, ({column} IS NOT NULL) AS addressable
            FROM recipient
            WHERE id = ANY($1::bigint[])
            """,
            recipient_ids,
        )
        address_flags[column] = {int(r["id"]): bool(r["addressable"]) for r in rows}

    resolved: dict[int, tuple[int, bool]] = {}
    for rid in recipient_ids:
        unit_id = units.get(rid)
        score = risks.get(unit_id, 0.0) if unit_id is not None else 0.0
        primary_id = _channel_from_steps(steps, score)
        primary_code = channel_codes.get(primary_id)
        if primary_code in AREA_CHANNELS:
            resolved[rid] = (primary_id, False)
            continue
        address_column = CHANNEL_ADDRESS_COLUMN.get(primary_code or "")
        if address_column is None:
            resolved[rid] = (primary_id, False)
            continue
        if address_flags[address_column].get(rid, False):
            resolved[rid] = (primary_id, False)
        elif simulate_fallback and sim_id is not None:
            resolved[rid] = (int(sim_id), True)
        else:
            resolved[rid] = (primary_id, False)
    return resolved
