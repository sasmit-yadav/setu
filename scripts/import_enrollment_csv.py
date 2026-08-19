#!/usr/bin/env python
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.env_loader import load_env_file


async def main() -> int:
    load_env_file(ROOT / ".env")
    env_file = os.environ.get("SETU_ENV_FILE")
    if env_file:
        load_env_file(Path(env_file), override=True)
    import asyncpg

    from services.enrollment.csv_import import import_csv

    csv_dir = ROOT / "data" / "enrollment"
    files = sorted(csv_dir.glob("*.csv"))
    if not files:
        print(f"No CSV files in {csv_dir} — run: python scripts/generate_enrollment_template.py")
        return 0
    dsn = os.environ.get("DATABASE_URL_DIRECT", "postgresql://setu:setu@localhost:5433/setu")
    conn = await asyncpg.connect(dsn=dsn)
    try:
        for path in files:
            content = path.read_bytes()
            print(f"dry_run {path.name}")
            dry = await import_csv(conn, content, dry_run=True, actor="bootstrap")
            print(
                f"  would_insert={dry.inserted} skipped={dry.skipped} rejected={dry.rejected}"
            )
            if dry.rejected and not dry.inserted:
                print(f"  skipped live import for {path.name}")
                continue
            live = await import_csv(
                conn,
                content,
                dry_run=False,
                actor="bootstrap",
                preview_token=dry.preview_token,
            )
            print(
                f"  live inserted={live.inserted} skipped={live.skipped} rejected={live.rejected}"
            )
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
