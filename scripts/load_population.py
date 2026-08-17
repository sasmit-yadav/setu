#!/usr/bin/env python
"""scripts/load_population.py — zonal population sum per admin_unit (§4.2's
`admin_unit.population` column), using rasterio (build-time only, §1.5.1).

Usage:
    python scripts/load_population.py --level 3
    python scripts/load_population.py --level 5

Reads geometry back OUT of Postgres (as GeoJSON) rather than re-parsing the
source file, so it stays correct even if load_admin_units.py's dedup/filter
logic changes — there is exactly one place that decides which units exist.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg
import rasterio
from rasterio.mask import mask
from shapely.geometry import shape


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
    p = argparse.ArgumentParser()
    p.add_argument("--level", type=int, required=True, choices=[3, 5])
    p.add_argument("--raster", default="data/raw/ind_pop.tif")
    args = p.parse_args()

    if not os.path.exists(args.raster):
        print(f"REFUSING: {args.raster} not found. Run scripts/fetch_data.sh first.", file=sys.stderr)
        return 1

    conn = psycopg.connect(db_url())
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, ST_AsGeoJSON(geom) FROM admin_unit WHERE level = %s", (args.level,)
        )
        rows = cur.fetchall()

    print(f"  {len(rows)} admin_unit rows at level {args.level}")
    if not rows:
        print("  Nothing to do — run load_admin_units.py first.")
        return 0

    updated = 0
    with rasterio.open(args.raster) as src:
        with conn.cursor() as cur:
            for i, (unit_id, geojson_str) in enumerate(rows):
                geom = json.loads(geojson_str)
                try:
                    out_image, _ = mask(src, [geom], crop=True, nodata=0, filled=True)
                except ValueError:
                    # Geometry doesn't overlap the raster window at all — leave population NULL.
                    continue
                band = out_image[0]
                total = float(band[band > 0].sum())
                cur.execute(
                    "UPDATE admin_unit SET population = %s WHERE id = %s",
                    (int(round(total)), unit_id),
                )
                updated += 1
                if (i + 1) % 200 == 0:
                    conn.commit()
                    print(f"  ... {i + 1}/{len(rows)}")
    conn.commit()
    conn.close()
    print(f"  DONE: population set on {updated}/{len(rows)} units")
    return 0


if __name__ == "__main__":
    sys.exit(main())
