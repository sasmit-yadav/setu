from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_assurance_ladder_announces_not_applicable():
    text = (ROOT / "web" / "console" / "src" / "components" / "AssuranceLadder.tsx").read_text(
        encoding="utf-8"
    )
    assert "sr-only" in text
    assert "not applicable" in text


# The landmark labels moved into i18n when the console gained its language
# switcher, so asserting on literal English in the TSX no longer proves
# anything — a page could lose the label entirely and still contain the word
# "Incident". Each entry is (filename, aria-label i18n key) and the check is
# two-sided: the page must label that section, and the key must resolve to a
# real English string. Grepping for the raw label would now also push English
# back into the TSX, which the hardcoding guard exists to prevent.
LANDMARKS = [
    ("Incident.tsx", "incident.versions"),
    ("AssistanceQueue.tsx", "queue.casesAria"),
    ("CommandBoard.tsx", "board.openIncidents"),
    ("Methodology.tsx", "method.channels"),
]


def test_four_event_screens_have_landmarks():
    i18n = (ROOT / "web" / "console" / "src" / "lib" / "i18n.tsx").read_text(encoding="utf-8")
    for filename, key in LANDMARKS:
        text = (ROOT / "web" / "console" / "src" / "pages" / filename).read_text(encoding="utf-8")
        assert f'aria-label={{t("{key}")}}' in text, f"{filename} lost its {key} landmark"
        assert f'"{key}": "' in i18n, f"{key} has no English string"


def test_assistance_queue_is_a_real_table():
    text = (ROOT / "web" / "console" / "src" / "pages" / "AssistanceQueue.tsx").read_text(
        encoding="utf-8"
    )
    assert 'role="table"' in text
