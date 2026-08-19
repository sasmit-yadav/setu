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

ROW_PATTERN = re.compile(
    r"\(\s*'((?:[^']|'')*)'"      # key
    r"\s*,\s*'((?:[^']|'')*)'"    # value
    r"\s*,\s*'((?:[^']|'')*)'"    # unit
    r"\s*,\s*'((?:[^']|'')*)'"    # note
    r"\s*\)",
    re.DOTALL,  # a note may span lines, and several legitimately do
)
# Every value-tuple in the seed starts a line with (' — used to cross-check
# that the parser saw as many rows as the file actually contains.
ROW_START_PATTERN = re.compile(r"^\s*\('((?:[^']|'')*)'", re.MULTILINE)


def parse_rows(sql: str) -> list[tuple[str, str, str | None, str | None]]:
    """Parse (key, value, unit, note) tuples out of 04_app_config.sql.

    re.DOTALL matters: the original pattern used [^'] for value/unit without
    DOTALL, so it only matched tuples written entirely on one line. A row
    whose `note` wrapped across lines — which several legitimately do, since
    the notes are written to be read aloud in Q&A — was SILENTLY SKIPPED. It
    never reached the database, and the script still printed a confident
    "Upserted N rows". A seed row that looks correct in git but does not exist
    in the database is precisely the drift this project's guards exist to make
    impossible.
    """
    rows = [
        (key.replace("''", "'"), value.replace("''", "'"),
         unit.replace("''", "'"), note.replace("''", "'"))
        for key, value, unit, note in ROW_PATTERN.findall(sql)
    ]

    # Fail loudly rather than under-applying. If these disagree, the seed file
    # has a tuple shape this parser cannot read — a hard error, not a quietly
    # smaller number.
    declared = [k.replace("''", "'") for k in ROW_START_PATTERN.findall(sql)]
    if len(rows) != len(declared):
        parsed_keys = {r[0] for r in rows}
        missing = [k for k in declared if k not in parsed_keys]
        raise SystemExit(
            f"upsert_app_config: parsed {len(rows)} rows but the seed file declares "
            f"{len(declared)}. Unparsed keys: {missing}. Refusing to apply a partial "
            f"config — fix the tuple formatting in 04_app_config.sql."
        )
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
