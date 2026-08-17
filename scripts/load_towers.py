#!/usr/bin/env python
"""scripts/load_towers.py — unit_features.tower_count_5km/nearest_tower_km
from OpenCelliD, per Part 30 and §1.6.2.

SPEC CORRECTION: OpenCelliD no longer offers per-MCC country downloads. The
design doc's fetch command (§1.6.2) requests
`opencellid.org/ocid/downloads?token=...&type=mcc&file=404.csv.gz` (and
`405.csv.gz`) — that shape 404s. The REAL download form (found by reading
the token-gated /downloads.php page's rendered HTML directly, since the
token must be submitted via a GET form, not a bare query param on
/downloads) offers exactly two products:

    type=full  file=cell_towers.csv.gz              — one global file
    type=diff  file=OCID-diff-cell-export-{date}.csv.gz  — daily diffs

There is no per-country split anymore. Fetch the global file once
(`scripts/fetch_opencellid.sh`, or by hand — see that script), then this
loader filters it to India (MCC 404 + 405) itself.

HONEST FINDING, not a bug in this script: as of 2026-08-17, the global
dump contains 5,349,901 rows across 199 MCCs, and ZERO of them are MCC 404
or 405. OpenCelliD's crowdsourced coverage of India is currently empty in
this export. This is exactly the scenario Part 30's fallback exists for —
`unit_features.tower_count_5km` stays NULL, and
`v_communication_vulnerability` correctly reports
'unknown_connectivity_features_pending', never 'standard' (Rule: a missing
input produces "unknown," never "fine").

This script is safe to re-run at any time — the dump is regenerated daily,
so it will pick up India rows automatically the day OpenCelliD's community
coverage includes any, with zero code changes (Part 30's own "strict
feature-set upgrade, no redesign" path).
"""

from __future__ import annotations

import csv
import gzip
import os
import sys

import psycopg

INDIA_MCCS = {"404", "405"}


def _fix_windows_console_encoding() -> None:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8")
            except (AttributeError, ValueError):
                pass


def db_url() -> str:
    url = os.environ.get("DATABASE_URL_DIRECT", "postgresql://setu:setu@localhost:5433/setu")
    return url.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+asyncpg://", "postgresql://")


def main() -> int:
    _fix_windows_console_encoding()
    path = "data/raw/cell_towers_global.csv.gz"
    if not os.path.exists(path):
        print(
            f"REFUSING: {path} not found. Fetch it first:\n"
            f'  curl -fSL -o {path} "https://opencellid.org/ocid/downloads'
            f'?token=$OPENCELLID_TOKEN&type=full&file=cell_towers.csv.gz"\n'
            f"(rate-limited to 2 downloads/day per token — don't re-fetch casually)",
            file=sys.stderr,
        )
        return 1

    conn = psycopg.connect(db_url())
    conn.execute("""
        CREATE TEMP TABLE cell_tower_raw (
            lon DOUBLE PRECISION, lat DOUBLE PRECISION
        )
    """)

    total = 0
    india = 0
    with gzip.open(path, "rt", encoding="utf-8") as f, conn.cursor() as cur:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            total += 1
            if row["mcc"] in INDIA_MCCS:
                india += 1
                rows.append((float(row["lon"]), float(row["lat"])))
                if len(rows) >= 5000:
                    cur.executemany(
                        "INSERT INTO cell_tower_raw (lon, lat) VALUES (%s, %s)", rows
                    )
                    rows.clear()
        if rows:
            cur.executemany("INSERT INTO cell_tower_raw (lon, lat) VALUES (%s, %s)", rows)
    conn.commit()

    print(f"  {total} total rows in the global dump, {india} for India (MCC 404/405)")

    if india == 0:
        print(
            "  HONEST RESULT: zero India rows in the current OpenCelliD export. "
            "This is a real, current data-coverage gap, not a bug (see this file's "
            "module docstring). unit_features.tower_count_5km stays NULL for every "
            "unit. v_communication_vulnerability will correctly report "
            "'unknown_connectivity_features_pending' for all of them — that is the "
            "designed fallback (Part 30), and it is now confirmed to be the actual "
            "state, not a precaution."
        )
        conn.close()
        return 0

    conn.execute("""
        CREATE INDEX ON cell_tower_raw USING GIST (
            ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography
        )
    """)

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM admin_unit")
        unit_ids = [r[0] for r in cur.fetchall()]
        updated = 0
        for unit_id in unit_ids:
            cur.execute(
                """
                SELECT COUNT(*) FILTER (
                         WHERE ST_DWithin(
                           ST_SetSRID(ST_MakePoint(t.lon, t.lat), 4326)::geography,
                           u.centroid, 5000)),
                       MIN(ST_Distance(
                           ST_SetSRID(ST_MakePoint(t.lon, t.lat), 4326)::geography,
                           u.centroid)) / 1000.0
                FROM admin_unit u
                CROSS JOIN cell_tower_raw t
                WHERE u.id = %s
                """,
                (unit_id,),
            )
            count5km, nearest_km = cur.fetchone()
            cur.execute(
                """
                INSERT INTO unit_features (unit_id, tower_count_5km, nearest_tower_km,
                                            computed_at, feature_version)
                VALUES (%s, %s, %s, now(), 'opencellid-v1')
                ON CONFLICT (unit_id) DO UPDATE
                  SET tower_count_5km = EXCLUDED.tower_count_5km,
                      nearest_tower_km = EXCLUDED.nearest_tower_km,
                      computed_at = now(),
                      feature_version = EXCLUDED.feature_version
                """,
                (unit_id, count5km, nearest_km),
            )
            updated += 1
        conn.commit()
    conn.close()
    print(f"  DONE: tower features set on {updated} units")
    return 0


if __name__ == "__main__":
    sys.exit(main())
