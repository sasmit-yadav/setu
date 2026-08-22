"""B3 — policy-driven retry and channel escalation, with zero hardcoded timings.

`escalation_policy` has carried `wait_before_next_s`, `backoff_multiplier`,
`jitter_ms` and `max_attempts` since migration 0002, fully seeded per severity
— and nothing read them. The consequence was not a missing nicety: every
delivery in the system's history was `attempt = 1`, the `escalated` state had
zero rows, and 462 failures were abandoned after a single try on a single
channel. A transient failure was a permanent one.

That also quietly broke B9's semantics. `on_channels_exhausted()` fired on the
*first* ChannelUnavailable, so "this unit exhausted push, SMS and IVR" was true
of one attempt on one channel. The human relay is meant to be the last resort
after the policy chain is genuinely spent; escalating to a human on the first
hiccup is both wrong and expensive (a human's time is the costliest channel in
the whole table, which is why `cost_weight` ranks it 12).

Part 24 exists to close v2.1's loose end #4 — "a flat `wait_before_next_s`
treats a channel down for one second the same as one down for ten minutes." So
the delay grows geometrically per attempt and carries jitter, because a fixed
cadence across a whole fan-out is a thundering herd aimed at a provider that
is already struggling.

Design notes:

* The due-time queue is the `zset:retry` sorted set that `keys.py` already
  reserved. Score is the epoch second the delivery becomes eligible, so
  draining is a single ZRANGEBYSCORE and the schedule survives a worker
  restart — an in-process `asyncio.sleep` would lose every pending retry when
  the worker is redeployed, which is precisely when retries matter.
* `compute_delay_s` is pure and takes the policy row as arguments rather than
  reading the database, so the growth-and-jitter behaviour is testable without
  a fixture and provable in a captured log (Part 19).
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any

import asyncpg
from redis.asyncio import Redis

from services.audit.ledger import append_audit
from services.delivery.keys import keys
from services.delivery.state_machine import transition
from services.delivery.states import State

# Milliseconds per second. A unit conversion, not a policy: the same test
# Part 38 applies in worker.py — nobody could reasonably want this different.
MS_PER_SECOND = 1000


@dataclass(frozen=True)
class PolicyStep:
    """One row of escalation_policy, for the channel a delivery is currently on."""

    step_order: int
    channel_id: int
    wait_before_next_s: int
    backoff_multiplier: float
    jitter_ms: int
    max_attempts: int


def compute_delay_s(
    attempt: int,
    *,
    wait_before_next_s: int,
    backoff_multiplier: float,
    jitter_ms: int,
    rng: random.Random | None = None,
) -> float:
    """Delay before `attempt` (1-based) is retried.

    Geometric growth on the policy's base wait, plus symmetric jitter. Jitter is
    +/- half the configured window so the *mean* stays on the policy's curve —
    adding only positive jitter would silently stretch every retry schedule
    beyond what the policy says, which is the sort of drift that makes a tuned
    backoff untunable.

    Clamped at zero: a policy row may legitimately set `wait_before_next_s = 0`
    (the siren step does), and jitter must not make that negative.
    """
    if attempt < 1:
        raise ValueError("attempt is 1-based")
    base = float(wait_before_next_s) * (float(backoff_multiplier) ** (attempt - 1))
    if jitter_ms:
        r = rng or random
        spread = (jitter_ms / MS_PER_SECOND) / 2.0
        base += r.uniform(-spread, spread)
    return max(0.0, base)


async def _policy_for(
    conn: asyncpg.Connection, severity: str, channel_id: int
) -> PolicyStep | None:
    """The policy step a delivery on `channel_id` is treated as occupying.

    A channel can appear at more than one step_order: `extreme` lists `sms` at
    step 0 (the Palghar fix — high predicted reach-risk skips push and starts on
    SMS) and again at step 2 (the normal position after push). `delivery` does
    not record which step it came from, so this takes the LAST matching step
    rather than the first.

    That is deliberate, and it is a heuristic: resolving `sms` to step 0 would
    escalate a failed SMS *back* to push at step 1 — the channel the policy
    deliberately skipped because reach-risk was high. Resolving to the last
    occurrence walks forward (sms -> ivr -> siren -> human_relay), which is the
    direction escalation is supposed to go. If a policy ever needs true
    per-step resumption, the honest fix is a `step_order` column on `delivery`,
    not a cleverer query.
    """
    row = await conn.fetchrow(
        """
        SELECT step_order, channel_id, wait_before_next_s, backoff_multiplier,
               jitter_ms, max_attempts
        FROM escalation_policy
        WHERE severity = $1 AND channel_id = $2
        ORDER BY step_order DESC
        LIMIT 1
        """,
        severity,
        channel_id,
    )
    return _as_step(row) if row else None


async def _next_step_after(
    conn: asyncpg.Connection, severity: str, step_order: int
) -> PolicyStep | None:
    row = await conn.fetchrow(
        """
        SELECT step_order, channel_id, wait_before_next_s, backoff_multiplier,
               jitter_ms, max_attempts
        FROM escalation_policy
        WHERE severity = $1 AND step_order > $2
        ORDER BY step_order ASC
        LIMIT 1
        """,
        severity,
        step_order,
    )
    return _as_step(row) if row else None


def _as_step(row: Any) -> PolicyStep:
    return PolicyStep(
        step_order=int(row["step_order"]),
        channel_id=int(row["channel_id"]),
        wait_before_next_s=int(row["wait_before_next_s"]),
        backoff_multiplier=float(row["backoff_multiplier"]),
        jitter_ms=int(row["jitter_ms"]),
        max_attempts=int(row["max_attempts"]),
    )


async def schedule_retry(
    redis: Redis,
    delivery_id: int,
    delay_s: float,
    *,
    now: float | None = None,
) -> float:
    """Make `delivery_id` eligible for another send after `delay_s`. Returns the
    due epoch second, so a caller can log or assert on the schedule."""
    due = (now if now is not None else time.time()) + delay_s
    await redis.zadd(keys.zset_retry(), {str(delivery_id): due})
    return due


async def is_held_for_later(
    redis: Redis, delivery_id: int, *, now: float | None = None
) -> bool:
    """True when this delivery is on zset:retry and not due yet.

    Severe phone-blast rows sit here until the previous channel's
    wait_before_next_s has elapsed. The worker must not send them on the
    first fan-out pass.
    """
    score = await redis.zscore(keys.zset_retry(), str(delivery_id))
    if score is None:
        return False
    cutoff = now if now is not None else time.time()
    return float(score) > cutoff


async def hold_staggered_channels(
    conn: asyncpg.Connection, redis: Redis, alert_id: int
) -> dict[int, float]:
    """Hold every channel after the first so Severe does not fire like Extreme.

    Extreme inserts the same SMS+IVR+FCM set and sends them immediately.
    Severe inserts that set then parks later channels on zset:retry. Delay
    before channel N is the sum of wait_before_next_s on the preceding
    policy steps (attempt 1, no jitter — a demo stagger must be the seeded
    wait, not a random draw).

    Returns {delivery_id: delay_s} for the held rows.
    """
    severity = await conn.fetchval("SELECT severity FROM alert WHERE id = $1", alert_id)
    if str(severity) != "severe":
        return {}
    policy_rows = await conn.fetch(
        """
        SELECT channel_id, step_order, wait_before_next_s
        FROM escalation_policy
        WHERE severity = $1
        """,
        str(severity),
    )
    wait_by_channel = {
        int(row["channel_id"]): int(row["wait_before_next_s"]) for row in policy_rows
    }
    order_by_channel = {int(row["channel_id"]): int(row["step_order"]) for row in policy_rows}
    unknown_order = 0
    for row in policy_rows:
        unknown_order = max(unknown_order, int(row["step_order"]))
    unknown_order = unknown_order + 1

    pending = await conn.fetch(
        """
        SELECT d.id, d.recipient_id, d.channel_id
        FROM delivery d
        JOIN channel c ON c.id = d.channel_id
        WHERE d.alert_id = $1 AND d.state = 'pending' AND d.attempt = 1
          AND c.code = ANY($2::text[])
        """,
        alert_id,
        ["sms", "ivr", "fcm"],
    )
    by_recipient: dict[int, list[tuple[int, int]]] = {}
    for row in pending:
        by_recipient.setdefault(int(row["recipient_id"]), []).append(
            (int(row["id"]), int(row["channel_id"]))
        )

    held: dict[int, float] = {}
    for group in by_recipient.values():
        ordered = sorted(
            group,
            key=lambda item: (order_by_channel.get(item[1], unknown_order), item[0]),
        )
        elapsed = 0.0
        previous_wait: int | None = None
        for index, (delivery_id, channel_id) in enumerate(ordered):
            if index > 0 and previous_wait is not None:
                delay = compute_delay_s(
                    1,
                    wait_before_next_s=previous_wait,
                    backoff_multiplier=1,
                    jitter_ms=0,
                )
                elapsed = elapsed + delay
                await schedule_retry(redis, delivery_id, elapsed)
                held[delivery_id] = elapsed
            previous_wait = wait_by_channel.get(channel_id, previous_wait)
    return held


async def due_delivery_ids(
    redis: Redis, *, now: float | None = None, limit: int = 100
) -> list[int]:
    """Deliveries whose retry time has arrived, removed from the queue.

    ZPOPMIN-style claim rather than a read-then-delete: two workers draining
    concurrently must not both pick up the same delivery, or one failure
    becomes two sends to the same person.
    """
    cutoff = now if now is not None else time.time()
    ids: list[int] = []
    for _ in range(limit):
        popped = await redis.zpopmin(keys.zset_retry(), 1)
        if not popped:
            break
        member, score = popped[0]
        if float(score) > cutoff:
            # Not due yet — put it back and stop; the set is score-ordered, so
            # nothing after this is due either.
            await redis.zadd(keys.zset_retry(), {member: float(score)})
            break
        ids.append(int(member))
    return ids


async def handle_failure(
    conn: asyncpg.Connection,
    redis: Redis,
    delivery_id: int,
    *,
    reason: str,
) -> dict[str, Any]:
    """Decide what happens after a failed send: retry, escalate, or exhaust.

    Returns a dict describing the decision, which the caller audits and the
    tests assert on. Deliberately does NOT itself send — the worker owns
    sending, this owns policy.
    """
    row = await conn.fetchrow(
        """
        SELECT d.id, d.alert_id, d.recipient_id, d.channel_id, d.attempt,
               a.severity
        FROM delivery d
        JOIN alert a ON a.id = d.alert_id
        WHERE d.id = $1
        """,
        delivery_id,
    )
    if row is None:
        return {"decision": "unknown_delivery"}

    severity = str(row["severity"])
    attempt = int(row["attempt"])
    step = await _policy_for(conn, severity, int(row["channel_id"]))
    if step is None:
        # The delivery is on a channel this severity's policy does not list —
        # e.g. the simulated carrier, which is a fallback rather than a policy
        # step. Nothing to retry against, and inventing a schedule would be a
        # hardcoded timing.
        return {"decision": "no_policy_for_channel", "channel_id": int(row["channel_id"])}

    if attempt < step.max_attempts:
        delay = compute_delay_s(
            attempt,
            wait_before_next_s=step.wait_before_next_s,
            backoff_multiplier=step.backoff_multiplier,
            jitter_ms=step.jitter_ms,
        )
        next_attempt = attempt + 1
        # failed -> pending goes through the state machine, not a raw UPDATE, so
        # the transition is validated against LEGAL and lands in the ledger like
        # every other state change. The attempt counter and the reason clear are
        # this module's own bookkeeping.
        await transition(conn, delivery_id, State.pending, actor="system:retry", reason=reason)
        await conn.execute(
            "UPDATE delivery SET attempt = $2, failed_reason = NULL WHERE id = $1",
            delivery_id,
            next_attempt,
        )
        due = await schedule_retry(redis, delivery_id, delay)
        await append_audit(
            conn,
            alert_id=int(row["alert_id"]),
            delivery_id=delivery_id,
            event_type="delivery.retry_scheduled",
            payload={
                "attempt": next_attempt,
                "max_attempts": step.max_attempts,
                "delay_s": round(delay, 3),
                "reason": reason,
            },
            actor="system:retry",
        )
        return {
            "decision": "retry",
            "attempt": next_attempt,
            "delay_s": delay,
            "due": due,
        }

    # This channel is spent. Move to the next step in the policy chain.
    nxt = await _next_step_after(conn, severity, step.step_order)
    if nxt is None:
        return {"decision": "chain_exhausted", "last_step": step.step_order}

    escalated = await conn.fetchval(
        """
        INSERT INTO delivery (alert_id, recipient_id, channel_id, state, attempt, simulated)
        VALUES ($1, $2, $3, 'pending', 1, false)
        ON CONFLICT (alert_id, recipient_id, channel_id, attempt) DO NOTHING
        RETURNING id
        """,
        int(row["alert_id"]),
        int(row["recipient_id"]),
        nxt.channel_id,
        )
    if escalated is None:
        # A delivery on the next channel already exists (a previous escalation,
        # or the fan-out put them on it directly). Not an error — just nothing
        # new to create.
        return {"decision": "already_on_next_channel", "channel_id": nxt.channel_id}

    # The spent delivery becomes `escalated`, not `failed`: the recipient has not
    # been abandoned, responsibility moved to another channel. That distinction
    # is what the console's per-channel assurance rests on, and it is why the
    # state exists in the enum at all — until now it had zero rows.
    await transition(
        conn, delivery_id, State.escalated, actor="system:escalation", reason=reason
    )

    # NOT "delivery.escalated": the state machine already emits that name for
    # the state change itself (it emits `delivery.<state>` for every
    # transition), and two events sharing a name with different payload shapes
    # makes the timeline ambiguous to read. This one carries the channel pair
    # and the attempts spent — the "why", next to the state machine's "what".
    await append_audit(
        conn,
        alert_id=int(row["alert_id"]),
        delivery_id=delivery_id,
        event_type="delivery.channel_escalated",
        payload={
            "from_channel_id": int(row["channel_id"]),
            "to_channel_id": nxt.channel_id,
            "from_step": step.step_order,
            "to_step": nxt.step_order,
            "attempts_spent": attempt,
            "reason": reason,
        },
        actor="system:escalation",
    )
    delay = compute_delay_s(
        1,
        wait_before_next_s=nxt.wait_before_next_s,
        backoff_multiplier=nxt.backoff_multiplier,
        jitter_ms=nxt.jitter_ms,
    )
    due = await schedule_retry(redis, int(escalated), delay)
    return {
        "decision": "escalated",
        "new_delivery_id": int(escalated),
        "to_channel_id": nxt.channel_id,
        "delay_s": delay,
        "due": due,
    }
