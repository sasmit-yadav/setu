#!/usr/bin/env python
"""scripts/verify_seeds.py — assert the seed data actually landed (Part 37.6).

⚠ Deliberately does NOT hard-code "74 app_config rows / 8 channel_capability
rows" the way §37.2's doctor.py and Part 19's DoD checklist do. Counting the
INSERTs in data/seeds/*.sql as actually written: 04_app_config.sql has ~68
rows and 02_channel_capability.sql seeds channel_capability_tier (4 tiers x 8
channels = 32 rows), not a one-row-per-channel channel_capability table —
because §5.2's single not_applicable_reason column can't hold more than one
reason per channel (fixed in migration 0009; see its docstring). Asserting the
spec's stale numbers here would make this script the second place the count
drifted, not the fix for the first.

Run this after `python run.py seed`. Never fails silently — every assertion
names the exact row it's checking, so a drift is a one-line diff to find.
"""

from __future__ import annotations

import asyncio
import os
import sys

import asyncpg


async def scalar(conn: asyncpg.Connection, sql: str) -> int:
    return await conn.fetchval(sql)


async def main() -> int:
    url = os.environ.get("DATABASE_URL_DIRECT", "postgresql://setu:setu@localhost:5433/setu")
    dsn = url.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn=dsn)
    failures: list[str] = []

    def check(label: str, actual: int, minimum: int) -> None:
        ok = actual >= minimum
        print(f"  {'OK ' if ok else 'FAIL'} {label}: {actual} (need >= {minimum})")
        if not ok:
            failures.append(label)

    check("channel rows", await scalar(conn, "SELECT COUNT(*) FROM channel"), 8)
    check("channel_capability_tier rows", await scalar(conn, "SELECT COUNT(*) FROM channel_capability_tier"), 32)
    # §21.1: extreme 1-5 (5) + extreme step_order=0 (1) + severe 1-4 (4)
    # + moderate 1-2 (2) + minor 1 (1) = 13.
    check("escalation_policy rows", await scalar(conn, "SELECT COUNT(*) FROM escalation_policy"), 13)
    check("alert_source rows", await scalar(conn, "SELECT COUNT(*) FROM alert_source"), 4)
    check("app_config rows", await scalar(conn, "SELECT COUNT(*) FROM app_config"), 110)

    # Rule 8, mechanically: every unsupported tier MUST carry a reason —
    # channel_capability_tier's own CHECK constraint already enforces this at
    # insert time, but re-verify here so a future manual INSERT can't slip past.
    unreasoned = await scalar(
        conn,
        "SELECT COUNT(*) FROM channel_capability_tier WHERE NOT supported AND not_applicable_reason IS NULL",
    )
    print(f"  {'OK ' if unreasoned == 0 else 'FAIL'} unsupported tiers with no reason: {unreasoned} (need 0)")
    if unreasoned:
        failures.append("channel_capability_tier missing reasons")

    # Every app_config row must have a non-empty note (Rule 1's whole point: a
    # threshold with no explanation is theatre, and Part 16's Day-4 DoD says
    # "every row has a non-empty note"). This used to only print INFO, with a
    # comment claiming severity.rank.* were deliberately exempt — but
    # severity.rank.extreme carried a note while its three siblings did not,
    # which is drift, not a policy. They now all have one, so this FAILS.
    empty_notes = await scalar(
        conn, "SELECT COUNT(*) FROM app_config WHERE note IS NULL OR trim(note) = ''"
    )
    total_config = await scalar(conn, "SELECT COUNT(*) FROM app_config")
    print(
        f"  {'OK ' if empty_notes == 0 else 'FAIL'} app_config rows with an empty note: "
        f"{empty_notes}/{total_config} (need 0)"
    )
    if empty_notes:
        failures.append("app_config rows with an empty note")

    # Part 16's Day-4 exit gate is "Zero alerts with a NULL incident_id".
    # Migration 0007 backfills it, but the column is nullable and nothing
    # re-checks it, so any alert inserted outside the composer path silently
    # breaks F2's version chain. Verified here because it is an invariant, not
    # a one-time migration step.
    orphan_alerts = await scalar(conn, "SELECT COUNT(*) FROM alert WHERE incident_id IS NULL")
    print(
        f"  {'OK ' if orphan_alerts == 0 else 'FAIL'} alerts with a NULL incident_id: "
        f"{orphan_alerts} (need 0)"
    )
    if orphan_alerts:
        failures.append("alerts with a NULL incident_id")

    await conn.close()

    if failures:
        print(f"\nFAILED: {len(failures)} check(s) did not meet their minimum.", file=sys.stderr)
        return 1
    print("\nverify_seeds: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
