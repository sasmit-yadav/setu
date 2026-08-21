#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.api.db import connect
from services.api.snapshot import LOAD_ORDER, SKIP_ROWS, SNAPSHOT_TABLES

SNAPSHOT_DIR = ROOT / "data" / "snapshots"


def _latest() -> Path:
    files = sorted(SNAPSHOT_DIR.glob("*.json"))
    if not files:
        raise SystemExit("no snapshot files in data/snapshots")
    return files[-1]


async def _columns(conn, table: str) -> dict[str, str]:
    rows = await conn.fetch(
        """
        SELECT column_name, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        """,
        table,
    )
    return {str(row["column_name"]): str(row["udt_name"]) for row in rows}


def _decode(value, udt: str):
    if value is None:
        return None
    if isinstance(value, dict) and "__ewkb__" in value:
        return bytes.fromhex(str(value["__ewkb__"]))
    if isinstance(value, dict) and "__hex__" in value:
        return bytes.fromhex(str(value["__hex__"]))
    if udt in {"timestamptz", "timestamp"} and isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if udt == "date" and isinstance(value, str):
        return datetime.fromisoformat(value).date()
    return value


async def _load(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tables = payload.get("tables") or {}
    conn = await connect()
    try:
        await conn.execute("SET session_replication_role = replica")
        for table in reversed(LOAD_ORDER):
            meta = tables.get(table) or {}
            if table in SKIP_ROWS or not meta.get("rows"):
                continue
            kind = meta.get("kind")
            if kind and kind != "BASE TABLE":
                continue
            exists = await conn.fetchval("SELECT to_regclass($1)", f"public.{table}")
            if exists is None:
                continue
            await conn.execute(f"DELETE FROM {table}")
        for table in LOAD_ORDER:
            meta = tables.get(table) or {}
            rows = meta.get("rows") or []
            if table in SKIP_ROWS or not rows:
                continue
            exists = await conn.fetchval("SELECT to_regclass($1)", f"public.{table}")
            if exists is None:
                continue
            types = await _columns(conn, table)
            for row in rows:
                cols = [c for c in row.keys() if c in types]
                if not cols:
                    continue
                values = [_decode(row[c], types[c]) for c in cols]
                placeholders = []
                bind: list = []
                idx = 1
                for col, value in zip(cols, values):
                    if types[col] == "geography":
                        placeholders.append(f"ST_SetSRID(ST_GeomFromEWKB(${idx}), 4326)::geography")
                    elif types[col] == "geometry":
                        placeholders.append(f"ST_SetSRID(ST_GeomFromEWKB(${idx}), 4326)")
                    else:
                        placeholders.append(f"${idx}")
                    bind.append(value)
                    idx += 1
                sql = (
                    f"INSERT INTO {table} ({', '.join(cols)}) "
                    f"VALUES ({', '.join(placeholders)}) "
                    f"ON CONFLICT DO NOTHING"
                )
                await conn.execute(sql, *bind)
        await conn.execute("SET session_replication_role = DEFAULT")
        await _advance_serials(conn)
    finally:
        await conn.close()


async def _advance_serials(conn) -> None:
    tables = await conn.fetch(
        """
        SELECT c.relname AS table_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'id' AND NOT a.attisdropped
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        """
    )
    for row in tables:
        table = str(row["table_name"])
        if not table.replace("_", "").isalnum():
            continue
        seq = await conn.fetchval("SELECT pg_get_serial_sequence($1, 'id')", table)
        if not seq:
            continue
        await conn.execute(
            f"SELECT setval($1::regclass, GREATEST(COALESCE((SELECT MAX(id) FROM {table}), 1), 1), true)",
            seq,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--path", type=Path, default=None)
    args = parser.parse_args()
    path = args.path or (_latest() if args.latest else None)
    if path is None:
        raise SystemExit("pass --path or --latest")
    asyncio.run(_load(path))
    nonempty = 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    for name, meta in (payload.get("tables") or {}).items():
        if name in SNAPSHOT_TABLES and int(meta.get("count") or 0):
            nonempty += 1
    print(f"loaded {path.name}: {nonempty} nonempty relations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
