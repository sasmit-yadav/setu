from __future__ import annotations

import pytest

from services.delivery.states import LEGAL, State


@pytest.mark.parametrize(
    ("frm", "to"),
    [
        (State.pending, State.queued),
        (State.queued, State.sent),
        (State.sent, State.delivered),
        (State.delivered, State.acknowledged),
        (State.failed, State.pending),
        (State.failed, State.escalated),
        (State.escalated, State.pending),
    ],
)
def test_legal_transitions(frm: State, to: State) -> None:
    assert to in LEGAL[frm]


@pytest.mark.parametrize(
    ("frm", "to"),
    [
        (State.pending, State.sent),
        (State.acknowledged, State.pending),
        (State.expired, State.queued),
    ],
)
def test_illegal_transitions(frm: State, to: State) -> None:
    assert to not in LEGAL[frm]
