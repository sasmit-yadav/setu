from __future__ import annotations

from enum import Enum


class State(str, Enum):
    pending = "pending"
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    acknowledged = "acknowledged"
    failed = "failed"
    expired = "expired"
    escalated = "escalated"


LEGAL: dict[State, frozenset[State]] = {
    State.pending: frozenset({State.queued, State.expired}),
    State.queued: frozenset({State.sent, State.failed, State.expired}),
    State.sent: frozenset({State.delivered, State.failed, State.expired}),
    State.delivered: frozenset({State.acknowledged, State.expired}),
    State.failed: frozenset({State.pending, State.escalated, State.expired}),
    State.escalated: frozenset({State.pending}),
    State.acknowledged: frozenset(),
    State.expired: frozenset(),
}

TIMESTAMP_COL: dict[State, str | None] = {
    State.queued: "queued_at",
    State.sent: "sent_at",
    State.delivered: "delivered_at",
    State.acknowledged: "acked_at",
    State.pending: None,
    State.failed: None,
    State.expired: None,
    State.escalated: None,
}


class IllegalTransition(Exception):
    def __init__(self, frm: State, to: State) -> None:
        super().__init__(f"{frm.value} → {to.value}")
        self.frm = frm
        self.to = to
