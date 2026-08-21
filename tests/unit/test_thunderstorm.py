from __future__ import annotations

from services.ingestion.adapters.thunderstorm import sigmoid


def test_sigmoid_midpoint_is_half():
    assert abs(sigmoid(0.0) - 0.5) < 1e-9


def test_sigmoid_is_monotone():
    assert sigmoid(-2.0) < sigmoid(0.0) < sigmoid(2.0)
