#!/usr/bin/env python
from __future__ import annotations

import asyncio
import csv
import os
import sys
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.env_loader import load_env_file


async def main() -> int:
    load_env_file(ROOT / ".env")
    import asyncpg

    from services.api import config_repo

    dsn = os.environ.get("DATABASE_URL_DIRECT", "postgresql://setu:setu@localhost:5433/setu")
    conn = await asyncpg.connect(dsn=dsn)
    try:
        out_dir = ROOT / "data" / "enrollment"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "recipients.csv"
        if out_path.exists():
            print(f"{out_path} already exists — not overwriting")
            return 0
        kl = await config_repo.get_str(conn, "case_study.bbox.KL")
        mh = await config_repo.get_str(conn, "case_study.bbox.MH")
        rows = await conn.fetch(
            """
            WITH boxes AS (
              SELECT 'KL'::text AS region,
                     split_part($1, ',', 1)::float8 AS south,
                     split_part($1, ',', 2)::float8 AS west,
                     split_part($1, ',', 3)::float8 AS north,
                     split_part($1, ',', 4)::float8 AS east
              UNION ALL
              SELECT 'MH',
                     split_part($2, ',', 1)::float8,
                     split_part($2, ',', 2)::float8,
                     split_part($2, ',', 3)::float8,
                     split_part($2, ',', 4)::float8
            )
            SELECT u.id, u.name, b.region,
                   COALESCE(uf.estimated_population, 0) AS pop
            FROM admin_unit u
            JOIN unit_features uf ON uf.unit_id = u.id
            JOIN boxes b ON ST_Intersects(
                u.geom,
                ST_MakeEnvelope(b.west, b.south, b.east, b.north, 4326)
            )
            WHERE u.level >= 3
            ORDER BY uf.estimated_population DESC NULLS LAST
            LIMIT 20
            """,
            kl,
            mh,
        )
        if not rows:
            print("No admin units in case-study bbox — run geometry pipeline first")
            return 1
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["phone", "unit_id", "preferred_lang", "push_token"])
        for idx, row in enumerate(rows):
            phone = f"+9199000{idx + 1:05d}"
            lang = "ml" if row["region"] == "KL" else "mr"
            writer.writerow([phone, row["id"], lang, ""])
        out_path.write_text(buffer.getvalue(), encoding="utf-8")
        print(f"Wrote {out_path} ({len(rows)} demo rows — replace phones and push_token before import)")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
