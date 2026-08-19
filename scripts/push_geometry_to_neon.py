#!/usr/bin/env python
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.env_loader import direct_dsn, load_env_file


def apply_relay_seed() -> None:
    import psycopg

    seeds = ROOT / "data" / "seeds" / "05_relay_nodes.sql"
    if not seeds.exists():
        return
    url = direct_dsn()
    with psycopg.connect(url) as conn, conn.cursor() as cur, seeds.open(encoding="utf-8") as fh:
        cur.execute(fh.read())
    print("Applied 05_relay_nodes.sql")


def main() -> int:
    neon_env = ROOT / ".env.neon"
    relay_only = "--relay-only" in sys.argv
    if neon_env.exists() and os.environ.get("SETU_ENV_FILE") is None:
        load_env_file(neon_env, override=True)
    elif relay_only:
        load_env_file(ROOT / ".env")
    if not os.environ.get("DATABASE_URL_DIRECT"):
        print("DATABASE_URL_DIRECT not set", file=sys.stderr)
        return 1
    target = os.environ["DATABASE_URL_DIRECT"].split("@")[-1]
    print(f"Geometry target -> {target}")
    if relay_only:
        apply_relay_seed()
        print("Relay seed complete.")
        return 0
    result = subprocess.run([sys.executable, "scripts/run_geometry_pipeline.py"], cwd=ROOT)
    if result.returncode != 0:
        return result.returncode
    apply_relay_seed()
    print("Geometry push complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
