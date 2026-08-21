#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "ml" / "dedup_heldout.json"


def main() -> int:
    pairs = []
    n = 0
    for i in range(80):
        lon = 76.08 + (i % 20) * 0.01
        lat = 11.72 + (i // 20) * 0.01
        pairs.append(
            {
                "id": n,
                "label": True,
                "a": {"lon": lon, "lat": lat, "t": "2024-07-30T10:00:00+00:00", "headline": f"Flood warning Wayanad {i}"},
                "b": {"lon": lon + 0.02, "lat": lat + 0.02, "t": "2024-07-30T12:00:00+00:00", "headline": f"Flooding reported near Wayanad {i}"},
            }
        )
        n += 1
    for i in range(40):
        lon = 76.08 + i * 0.01
        pairs.append(
            {
                "id": n,
                "label": False,
                "a": {"lon": lon, "lat": 11.72, "t": "2024-07-30T10:00:00+00:00", "headline": f"Flood warning Wayanad far {i}"},
                "b": {"lon": lon + 3.5, "lat": 15.22, "t": "2024-07-30T11:00:00+00:00", "headline": f"Flood warning Palghar {i}"},
            }
        )
        n += 1
    for i in range(40):
        pairs.append(
            {
                "id": n,
                "label": False,
                "a": {"lon": 76.1, "lat": 11.7, "t": "2024-07-30T10:00:00+00:00", "headline": f"Flood warning timed {i}"},
                "b": {"lon": 76.11, "lat": 11.71, "t": "2024-08-02T10:00:00+00:00", "headline": f"Flood warning timed {i}"},
            }
        )
        n += 1
    for i in range(20):
        pairs.append(
            {
                "id": n,
                "label": True,
                "a": {"lon": 76.1, "lat": 11.7, "t": "2024-07-30T10:00:00+00:00", "headline": "Wayanad flood same event"},
                "b": {"lon": 80.2, "lat": 13.1, "t": "2024-07-30T11:00:00+00:00", "headline": "Wayanad flood same event elsewhere"},
            }
        )
        n += 1
    for i in range(20):
        pairs.append(
            {
                "id": n,
                "label": False,
                "a": {"lon": 72.9, "lat": 19.5, "t": "2024-07-30T10:00:00+00:00", "headline": "Palghar landslide"},
                "b": {"lon": 72.91, "lat": 19.51, "t": "2024-07-30T10:30:00+00:00", "headline": "Palghar industrial fire"},
            }
        )
        n += 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"pairs": pairs}, indent=2), encoding="utf-8")
    print(f"{OUT} n={len(pairs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
