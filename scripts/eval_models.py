#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.api.db import connect
from services.ml.dedup_eval import evaluate_and_publish
from services.ml.reach_risk import validate_case_study

PAIRS = ROOT / "data" / "ml" / "dedup_heldout.json"


async def _run() -> None:
    if not PAIRS.exists():
        raise SystemExit(f"missing {PAIRS} — run scripts/gen_dedup_heldout.py")
    payload = json.loads(PAIRS.read_text(encoding="utf-8"))
    pairs = payload.get("pairs") or []
    conn = await connect()
    try:
        metrics = await evaluate_and_publish(conn, pairs)
        case = await validate_case_study(conn)
        print(
            "dedup",
            metrics.get("precision"),
            metrics.get("recall"),
            metrics.get("f1"),
            "n",
            metrics.get("held_out_n"),
        )
        print("case_study n", case.get("n"), "flagged", case.get("flagged"))
    finally:
        await conn.close()


def main() -> int:
    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
