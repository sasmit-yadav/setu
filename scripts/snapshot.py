#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.api.db import connect
from services.api.snapshot import SKIP_ROWS, SNAPSHOT_TABLES
DEFAULT_DIR = ROOT / "data" / "snapshots"


def _jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, memoryview)):
        return {"__hex__": bytes(value).hex()}
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


async def _columns(conn, table: str) -> list[tuple[str, str]]:
    rows = await conn.fetch(
        """
        SELECT column_name, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
        """,
        table,
    )
    return [(str(row["column_name"]), str(row["udt_name"])) for row in rows]


async def _dump() -> dict:
    conn = await connect()
    try:
        tables: dict[str, dict] = {}
        for table in SNAPSHOT_TABLES:
            rel = await conn.fetchval("SELECT to_regclass($1)", f"public.{table}")
            if rel is None:
                tables[table] = {"missing": True, "count": 0, "rows": []}
                continue
            kind = await conn.fetchval(
                """
                SELECT table_type FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = $1
                """,
                table,
            )
            count = await conn.fetchval(f"SELECT COUNT(*)::bigint FROM {table}")
            rows: list[dict] = []
            if table not in SKIP_ROWS and kind == "BASE TABLE":
                cols = await _columns(conn, table)
                select_parts = []
                for name, udt in cols:
                    if udt in {"geometry", "geography"}:
                        select_parts.append(
                            f"encode(ST_AsEWKB({name}::geometry), 'hex') AS {name}"
                        )
                    else:
                        select_parts.append(name)
                fetched = await conn.fetch(f"SELECT {', '.join(select_parts)} FROM {table}")
                geom = {name for name, udt in cols if udt in {"geometry", "geography"}}
                for row in fetched:
                    item = {}
                    for key, value in dict(row).items():
                        if key in geom and isinstance(value, str):
                            item[key] = {"__ewkb__": value}
                        else:
                            item[key] = _jsonable(value)
                    rows.append(item)
            tables[table] = {
                "missing": False,
                "kind": kind,
                "count": int(count or 0),
                "rows": rows,
            }
        return {"captured_at": datetime.now(timezone.utc).isoformat(), "tables": tables}
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
    out = args.out or (DEFAULT_DIR / f"{datetime.now(timezone.utc).date().isoformat()}.json")
    payload = asyncio.run(_dump())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
