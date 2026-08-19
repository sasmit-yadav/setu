#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import importlib
import os
import sys
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TIER_ATTR = {
    "provider_accept": "supports_provider_accept",
    "device_delivered": "supports_device_delivered",
    "opened": "supports_opened",
    "acknowledgement": "supports_acknowledgement",
}


def load_class(class_path: str):
    module_name, _, class_name = class_path.rpartition(".")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


async def main() -> int:
    url = os.environ.get("DATABASE_URL_DIRECT", "postgresql://setu:setu@localhost:5433/setu")
    dsn = url.replace("postgresql+psycopg://", "postgresql://").replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    conn = await asyncpg.connect(dsn=dsn)
    failures: list[str] = []
    rows = await conn.fetch(
        """
        SELECT c.id, c.code, c.class_path, t.tier, t.supported
        FROM channel c
        JOIN channel_capability_tier t ON t.channel_id = c.id
        ORDER BY c.code, t.tier
        """
    )
    by_channel: dict[str, tuple[str, type]] = {}
    for row in rows:
        code = row["code"]
        if code not in by_channel:
            try:
                cls = load_class(row["class_path"])
                by_channel[code] = (row["class_path"], cls)
            except Exception as exc:
                failures.append(f"{code}: cannot import {row['class_path']}: {exc}")
                continue
        _, cls = by_channel[code]
        attr = TIER_ATTR[row["tier"]]
        declared = bool(getattr(cls, attr, None))
        if declared != row["supported"]:
            failures.append(
                f"{code}.{row['tier']}: db={row['supported']} adapter={declared}"
            )
    await conn.close()
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("check_channel_capability: clean")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
