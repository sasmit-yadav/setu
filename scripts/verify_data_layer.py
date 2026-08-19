#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.env_loader import direct_dsn, load_env_file

CHECKS: list[tuple[str, str, int]] = [
    ("admin_unit", "SELECT COUNT(*) FROM admin_unit", 1),
    ("app_config", "SELECT COUNT(*) FROM app_config", 100),
    ("channel", "SELECT COUNT(*) FROM channel", 8),
    ("alert_source", "SELECT COUNT(*) FROM alert_source WHERE enabled", 1),
    ("safe_zone", "SELECT COUNT(*) FROM safe_zone", 1),
    ("relay_node", "SELECT COUNT(*) FROM relay_node", 1),
]


def main() -> int:
    env_path = Path(os.environ.get("SETU_ENV_FILE", ROOT / ".env"))
    load_env_file(env_path, override=bool(os.environ.get("SETU_ENV_FILE")))
    label = env_path.name
    url = direct_dsn()
    host = url.split("@")[-1] if "@" in url else url
    print(f"verify_data_layer ({label}) -> {host}")
    ok = True
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        for name, sql, minimum in CHECKS:
            cur.execute(sql)
            count = int(cur.fetchone()[0])
            status = "ok" if count >= minimum else "FAIL"
            if count < minimum:
                ok = False
            print(f"  {name}: {count} [{status}, need >={minimum}]")
        cur.execute(
            """
            SELECT COUNT(*) FROM recipient
            WHERE consented_at IS NOT NULL AND opted_out_at IS NULL
            """
        )
        recipients = int(cur.fetchone()[0])
        print(f"  consented_recipients: {recipients} [{'ok' if recipients else 'WARN — import CSV'}]")
        cur.execute(
            """
            SELECT u.id, u.name, COUNT(r.id) AS n
            FROM admin_unit u
            LEFT JOIN recipient r ON r.unit_id = u.id
              AND r.consented_at IS NOT NULL AND r.opted_out_at IS NULL
            WHERE u.level >= 3
            GROUP BY u.id, u.name
            HAVING COUNT(r.id) > 0
            ORDER BY n DESC
            LIMIT 5
            """
        )
        rows = cur.fetchall()
        if rows:
            print("  top_units_by_recipients:")
            for unit_id, name, n in rows:
                print(f"    {unit_id} {name}: {n}")
        try:
            cur.execute("SELECT version_num FROM alembic_version")
            print(f"  alembic: {cur.fetchone()[0]}")
        except psycopg.Error:
            conn.rollback()
            print("  alembic: missing")
            ok = False
    if not ok:
        print("\nverify_data_layer: FAILED")
        return 1
    print("\nverify_data_layer: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
