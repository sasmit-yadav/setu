#!/usr/bin/env python
"""scripts/load_terrain.py — terrain ruggedness + mean elevation per
admin_unit (unit_features.terrain_ruggedness/mean_elevation_m), from the
Copernicus GLO-30 DEM tiles fetched by fetch_data.sh.

Ruggedness here is a simple, documented proxy — std-deviation of elevation
within the unit's footprint, normalized by a config-free constant band
(0-500m std -> 0-1) — NOT a topographic ruggedness index (TRI) computation,
which would need neighbor-cell differencing across tile boundaries. Good
enough for D8f's "is this unit mountainous" question; the number in
`unit_features.feature_version` records which proxy produced it so a later
upgrade to real TRI is not a silent redefinition of the column's meaning.

Only covers units whose centroid falls in one of the four fetched DEM tiles
(Wayanad + Palghar, per Part 29) — everything else is correctly left NULL,
not zero, not guessed.
"""

from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np
import psycopg
import rasterio
from rasterio.mask import mask

FEATURE_VERSION = "std-dev-proxy-v1"
RUGGEDNESS_STD_CEILING_M = 500.0  # documented in this file, not app_config —
# this is a units-of-measurement choice about the proxy itself, not an
# operational policy someone would tune; app_config's vuln.terrain_ruggedness_ceiling
# (already seeded) is the separate, real policy threshold that reads this output.


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
    tiles = sorted(glob.glob("data/raw/dem/*.tif"))
    if not tiles:
        print("REFUSING: no tiles in data/raw/dem/. Run scripts/fetch_data.sh first.", file=sys.stderr)
        return 1
    print(f"  {len(tiles)} DEM tile(s): {[os.path.basename(t) for t in tiles]}")

    conn = psycopg.connect(db_url())
    with conn.cursor() as cur:
        cur.execute("SELECT id, ST_AsGeoJSON(geom) FROM admin_unit")
        rows = cur.fetchall()

    # Open every tile ONCE, outside the per-unit loop. The first version of
    # this script re-opened all 4 GeoTIFFs inside the unit loop — up to
    # ~33,000 file opens for 8,302 units, since most units (everything
    # outside Wayanad/Palghar) fail against every tile before being skipped.
    # Killed mid-run for taking too long; opening once and reusing the
    # dataset handles is the actual fix, not a bigger timeout.
    open_tiles = [rasterio.open(t) for t in tiles]

    updated = 0
    try:
        with conn.cursor() as cur:
            for i, (unit_id, geojson_str) in enumerate(rows):
                geom = json.loads(geojson_str)
                elevations = None
                for src in open_tiles:
                    try:
                        out_image, _ = mask(src, [geom], crop=True, filled=True)
                        band = out_image[0].astype("float64")
                        valid = band[(band > -1000) & (band < 9000)]  # drop nodata sentinels
                        if valid.size > 0:
                            elevations = valid
                            break
                    except ValueError:
                        continue  # geometry doesn't overlap this tile
                if (i + 1) % 1000 == 0:
                    print(f"  ... {i + 1}/{len(rows)} units checked, {updated} matched so far")
                if elevations is None or elevations.size == 0:
                    continue
                mean_elev = float(np.mean(elevations))
                std_elev = float(np.std(elevations))
                ruggedness = min(1.0, std_elev / RUGGEDNESS_STD_CEILING_M)
                cur.execute(
                    """
                    INSERT INTO unit_features (unit_id, terrain_ruggedness, mean_elevation_m,
                                                computed_at, feature_version)
                    VALUES (%s, %s, %s, now(), %s)
                    ON CONFLICT (unit_id) DO UPDATE
                      SET terrain_ruggedness = EXCLUDED.terrain_ruggedness,
                          mean_elevation_m = EXCLUDED.mean_elevation_m,
                          computed_at = now(),
                          feature_version = EXCLUDED.feature_version
                    """,
                    (unit_id, ruggedness, mean_elev, FEATURE_VERSION),
                )
                updated += 1
        conn.commit()
    finally:
        for src in open_tiles:
            src.close()
        conn.close()
    print(f"  DONE: {updated}/{len(rows)} units got terrain features "
          f"(the rest fall outside the 4 fetched tiles — correctly left NULL)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
