from __future__ import annotations

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


async def primary_channel_for_alert(conn: asyncpg.Connection, alert_id: int) -> int:
    severity = await conn.fetchval("SELECT severity FROM alert WHERE id = $1", alert_id)
    row = await conn.fetchrow(
        """
        SELECT channel_id
        FROM escalation_policy
        WHERE severity = $1
        ORDER BY step_order ASC
        LIMIT 1
        """,
        severity,
    )
    if row is None:
        raise ValueError(f"no escalation policy for severity {severity}")
    return int(row["channel_id"])


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

    primary_id = await primary_channel_for_alert(conn, alert_id)
    primary_code = await conn.fetchval("SELECT code FROM channel WHERE id = $1", primary_id)
    sim_id = await conn.fetchval("SELECT id FROM channel WHERE code = 'sim'")
    simulate_fallback = await config_repo.get_bool(
        conn, "delivery.simulate_when_unaddressable"
    )

    # An area-addressed channel needs no per-recipient address at all.
    if primary_code in AREA_CHANNELS:
        return {rid: (primary_id, False) for rid in recipient_ids}

    address_column = CHANNEL_ADDRESS_COLUMN.get(primary_code)
    if address_column is None:
        # Unknown channel: do not guess. Route as-is and let the send path
        # fail loudly with a named reason rather than silently simulating.
        return {rid: (primary_id, False) for rid in recipient_ids}

    # One query for the whole batch — not one per recipient. A 7,000-unit
    # alert must not become 7,000 round trips.
    rows = await conn.fetch(
        f"""
        SELECT id, ({address_column} IS NOT NULL) AS addressable
        FROM recipient
        WHERE id = ANY($1::bigint[])
        """,
        recipient_ids,
    )
    addressable = {int(r["id"]): bool(r["addressable"]) for r in rows}

    resolved: dict[int, tuple[int, bool]] = {}
    for rid in recipient_ids:
        if addressable.get(rid, False):
            resolved[rid] = (primary_id, False)
        elif simulate_fallback and sim_id is not None:
            resolved[rid] = (int(sim_id), True)
        else:
            # Config says do not simulate: route to the real channel and let it
            # fail with a named reason. "Unreachable" is a legitimate, useful
            # output — it is what D8f's vulnerability map is built from.
            resolved[rid] = (primary_id, False)
    return resolved
