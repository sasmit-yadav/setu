from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_assurance_ladder_announces_not_applicable():
    text = (ROOT / "web" / "console" / "src" / "components" / "AssuranceLadder.tsx").read_text(
        encoding="utf-8"
    )
    assert "sr-only" in text
    assert "not applicable" in text


def test_four_event_screens_have_landmarks():
    pages = {
        "Incident.tsx": ("Incident", 'aria-label="Version chain"'),
        "AssistanceQueue.tsx": ("Assistance queue", 'role="table"'),
        "CommandBoard.tsx": ("Command Board", "Select incident"),
        "Methodology.tsx": ("Methodology", 'aria-label="Channel capability"'),
    }
    for filename, needles in pages.items():
        text = (ROOT / "web" / "console" / "src" / "pages" / filename).read_text(encoding="utf-8")
        for needle in needles:
            assert needle in text
