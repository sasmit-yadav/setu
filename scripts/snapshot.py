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
        _reject_fabricated_translations(tables)
        return {"captured_at": datetime.now(timezone.utc).isoformat(), "tables": tables}
    finally:
        await conn.close()


# Placeholder translations written by test fixtures. `test_quality_gate.py`
# inserts 'Malayalam headline' to satisfy the translation_exists rule, and the
# stubbed ML client in `test_translate.py` returns an 'ml:'-prefixed string.
# Harmless in a dev database; catastrophic in a snapshot.
_FABRICATED_TRANSLATION_MARKERS = ("Malayalam headline", "Malayalam body")
_FABRICATED_TRANSLATION_PREFIXES = ("ml:", "hi:", "ta:", "bn:", "te:", "kn:", "mr:")


def _reject_fabricated_translations(tables: dict) -> None:
    """Refuse to write a snapshot containing invented translations.

    A snapshot is the artifact the demo actually loads (`python run.py demo`),
    so a fabricated row here is not a test smell — it is the platform asserting
    `translated=True` with no fallback notice while serving text no model ever
    produced. That is the single thing this project exists to argue against, and
    it would be on screen in the language the citizen reads.

    This fails rather than filtering. A snapshot with NO translations degrades
    honestly — the PWA shows the original language plus a visible notice — but a
    snapshot with fake ones lies, and silently dropping them would hide that the
    demo has no real translations at all, which is a decision the operator needs
    to make knowingly.
    """
    entry = tables.get("alert_translation") or {}
    bad: list[str] = []
    for row in entry.get("rows", []):
        for field in ("headline", "body"):
            text = str(row.get(field) or "")
            if text in _FABRICATED_TRANSLATION_MARKERS or text.startswith(
                _FABRICATED_TRANSLATION_PREFIXES
            ):
                bad.append(f"alert_id={row.get('alert_id')} lang={row.get('lang')} {field}={text!r}")
                break
    if not bad:
        return
    preview = "\n  ".join(bad[:5])
    more = f"\n  ... and {len(bad) - 5} more" if len(bad) > 5 else ""
    raise SystemExit(
        f"refusing to snapshot {len(bad)} fabricated alert_translation row(s).\n"
        f"  {preview}{more}\n\n"
        "These are test-fixture placeholders, not model output. Purge them, then\n"
        "re-run:\n\n"
        "  DELETE FROM alert_translation\n"
        "  WHERE headline IN ('Malayalam headline', 'Malayalam body')\n"
        "     OR headline ~ '^(ml|hi|ta|bn|te|kn|mr):';\n\n"
        "Real translations come from the HF Space (SETU_LOAD_ML_MODELS=1). Until\n"
        "it is deployed the cache stays empty and the PWA falls back honestly\n"
        "with translation.fallback_notice, which is the correct behaviour."
    )


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
