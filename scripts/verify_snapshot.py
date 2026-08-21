#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.api.snapshot import SNAPSHOT_TABLES
SNAPSHOT_DIR = ROOT / "data" / "snapshots"
BOARD_TABLES = (
    "incident",
    "alert",
    "delivery",
    "delivery_event",
    "citizen_response",
    "app_config",
    "channel_capability_tier",
)


def _latest() -> Path:
    files = sorted(SNAPSHOT_DIR.glob("*.json"))
    if not files:
        raise SystemExit("no snapshot files in data/snapshots")
    return files[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--path", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    path = args.path or (_latest() if args.latest else None)
    if path is None:
        raise SystemExit("pass --path or --latest")
    payload = json.loads(path.read_text(encoding="utf-8"))
    tables = payload.get("tables") or {}
    missing = [name for name in SNAPSHOT_TABLES if name not in tables or tables[name].get("missing")]
    if missing:
        raise SystemExit(f"snapshot missing tables: {missing}")
    if args.strict:
        empty = [name for name in BOARD_TABLES if int(tables[name].get("count") or 0) == 0]
        if empty:
            raise SystemExit(f"strict: board tables empty in snapshot: {empty}")
    print(f"ok {path} tables={len(tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
