#!/usr/bin/env python
"""Fill missing alert_translation rows via the ML HTTP service.

The Render API cannot reach a laptop :8001, so compose-time
ensure_translations no-ops in the cloud. This script talks to whatever
HF_SPACE_URL the parent set (worker-cloud / translate-cloud default that
to http://127.0.0.1:8001) and writes real IndicTrans2 output into Neon.

It never invents Malayalam. If /translate is down or returns empty, the
row is left missing and the PWA keeps showing the fallback notice.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.api.db import connect
from services.api.settings import settings
from services.ml.translate import ensure_translations


async def main_async() -> int:
    base = settings.hf_space_url.strip()
    if not base:
        print(
            "HF_SPACE_URL is empty — start `python run.py ml-load` and rerun "
            "via `python run.py translate-cloud`.",
            file=sys.stderr,
        )
        return 1
    conn = await connect()
    try:
        rows = await conn.fetch(
            """
            SELECT id, headline, lifecycle_status
            FROM alert
            WHERE lifecycle_status IN ('draft', 'active')
            ORDER BY id DESC
            """
        )
        if not rows:
            print("  no draft/active alerts")
            return 0
        filled = 0
        for row in rows:
            before = await conn.fetchval(
                "SELECT count(*) FROM alert_translation WHERE alert_id = $1",
                row["id"],
            )
            await ensure_translations(conn, int(row["id"]))
            after = await conn.fetchval(
                "SELECT count(*) FROM alert_translation WHERE alert_id = $1",
                row["id"],
            )
            added = int(after) - int(before)
            langs = await conn.fetch(
                "SELECT lang FROM alert_translation WHERE alert_id = $1 ORDER BY lang",
                row["id"],
            )
            codes = ",".join(str(item["lang"]) for item in langs) or "(none)"
            print(
                f"  alert {row['id']} ({row['lifecycle_status']}) "
                f"+{added} -> {codes}"
            )
            filled += added
        print(f"  done. {filled} new translation row(s) via {base}")
        return 0
    finally:
        await conn.close()


def main() -> int:
    if not os.environ.get("HF_SPACE_URL", "").strip():
        print("HF_SPACE_URL unset", file=sys.stderr)
        return 1
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
