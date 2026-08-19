#!/usr/bin/env python
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seeds" / "04_app_config.sql"
sys.path.insert(0, str(ROOT))

from scripts.env_loader import direct_dsn, load_env_file


def parse_rows(sql: str) -> list[tuple[str, str, str | None, str | None]]:
    rows: list[tuple[str, str, str | None, str | None]] = []
    pattern = re.compile(
        r"\(\s*'([^']+)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'((?:[^']|'')*)'\s*\)"
    )
    for match in pattern.finditer(sql):
        key, value, unit, note = match.groups()
        rows.append((key, value, unit, note.replace("''", "'")))
    return rows


def main() -> int:
    env_path = os.environ.get("SETU_ENV_FILE")
    if env_path:
        load_env_file(Path(env_path), override=True)
    else:
        load_env_file(ROOT / ".env")
    url = direct_dsn()
    sql = SEED.read_text(encoding="utf-8")
    rows = parse_rows(sql)
    upsert = """
        INSERT INTO app_config (key, value, unit, note)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value, unit = EXCLUDED.unit, note = EXCLUDED.note
    """
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        for row in rows:
            cur.execute(upsert, row)
    print(f"Upserted {len(rows)} app_config rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
