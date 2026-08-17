#!/usr/bin/env python
"""scripts/load_admin_units.py — load geoBoundaries geometry into admin_unit.

Written in pure Python (json + psycopg + PostGIS's ST_GeomFromGeoJSON)
instead of the design spec's ogr2ogr command (§1.6.2) because GDAL/ogr2ogr
is not installed on this machine, and installing it on Windows is its own
yak-shave. This avoids that dependency entirely — every other tool already
in requirements.txt (psycopg, shapely) is enough.

Usage:
    python scripts/load_admin_units.py --level 3
    python scripts/load_admin_units.py --level 5 --bbox 11.2,75.7,12.0,76.5 --bbox 19.3,72.5,20.1,73.3

Trap 4 (design spec §4.1): ADM5 nationwide is 649,771 polygons / ~1GB, which
does not fit Neon's free 0.5GB tier. --level 5 REQUIRES --bbox and refuses
to run without it — loading nationwide ADM5 by accident is exactly the
mistake that blows the free-tier budget on day one.

SPEC CORRECTION: §1.6.2's filter approach
(`-where "shapeGroup='IND' AND ADM1_NAME IN ('Kerala','Maharashtra')"`)
assumes an ADM1_NAME (state name) attribute that DOES NOT EXIST in
geoBoundaries' gbOpen ADM5 simplified files. Their actual properties are
only `shapeName`, `shapeISO` (usually empty), `shapeID`, `shapeGroup`
(always "IND" for this national extract), `shapeType`. There is no
state-level attribute to filter on at all — confirmed by inspecting a
sample feature directly. Filtering by a geometry bounding box instead,
scoped to the two case-study districts (Wayanad, Palghar) rather than the
two full states, which is a tighter and more defensible scope than the
spec's own approach, and matches how safe_zone/relay_node are already
bbox-scoped to the same two districts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import psycopg


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


def name_field(props: dict) -> str:
    for key in ("shapeName", "ADM3_NAME", "ADM5_NAME", "NAME_3", "NAME_5", "name"):
        if props.get(key):
            return str(props[key])
    return "UNKNOWN"


def geometry_bbox(geom: dict) -> tuple[float, float, float, float] | None:
    """Cheap min/max lon/lat over every coordinate in a Polygon/MultiPolygon,
    without constructing a shapely object for all 649K features — this is a
    filter pass, not a precision spatial op, and a bbox-overlap test is all
    that's needed to decide "is this feature anywhere near Wayanad/Palghar."
    """
    lons: list[float] = []
    lats: list[float] = []

    def walk(coords):
        if not coords:
            return
        if isinstance(coords[0], (int, float)):
            lons.append(coords[0])
            lats.append(coords[1])
        else:
            for c in coords:
                walk(c)

    walk(geom.get("coordinates"))
    if not lons:
        return None
    return (min(lats), min(lons), max(lats), max(lons))


def bbox_overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    a_s, a_w, a_n, a_e = a
    b_s, b_w, b_n, b_e = b
    return a_s <= b_n and a_n >= b_s and a_w <= b_e and a_e >= b_w


def lgd_field(props: dict) -> int | None:
    for key in ("shapeISO", "lgd_code", "LGD_CODE"):
        v = props.get(key)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.isdigit():
            return int(v)
    return None


def load(path: str, level: int, bboxes: list[tuple[float, float, float, float]] | None,
         batch_size: int) -> None:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data["features"]
    print(f"  {len(features)} features in {path}")

    if bboxes:
        before = len(features)
        kept = []
        for ft in features:
            fb = geometry_bbox(ft.get("geometry", {}))
            if fb and any(bbox_overlaps(fb, b) for b in bboxes):
                kept.append(ft)
        features = kept
        print(f"  filtered by {len(bboxes)} bbox(es): {before} -> {len(features)} features")
        if not features:
            print("  WARNING: 0 features after filtering — check the --bbox values "
                  "(format: south,west,north,east).")

    conn = psycopg.connect(db_url())
    conn.autocommit = False
    inserted = 0
    skipped_no_geom = 0
    t0 = time.monotonic()

    with conn.cursor() as cur:
        for i in range(0, len(features), batch_size):
            batch = features[i : i + batch_size]
            for ft in batch:
                geom = ft.get("geometry")
                if not geom:
                    skipped_no_geom += 1
                    continue
                props = ft.get("properties", {})
                # ST_Multi() upgrades a bare Polygon to MultiPolygon so every
                # row matches admin_unit.geom's declared type regardless of
                # whether the source feature was a Polygon or MultiPolygon.
                cur.execute(
                    """
                    INSERT INTO admin_unit (lgd_code, level, name, geom, source_id, fetched_at)
                    VALUES (%s, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)),
                            'geoboundaries', now())
                    ON CONFLICT (lgd_code) DO NOTHING
                    """,
                    (lgd_field(props), level, name_field(props), json.dumps(geom)),
                )
                inserted += cur.rowcount
            conn.commit()
            print(f"  ... {min(i + batch_size, len(features))}/{len(features)} processed, "
                  f"{inserted} inserted so far ({time.monotonic() - t0:.0f}s elapsed)")

    conn.close()
    print(f"  DONE: {inserted} rows inserted, {skipped_no_geom} features skipped (no geometry)")


def parse_bbox(s: str) -> tuple[float, float, float, float]:
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--bbox needs 4 comma-separated values: south,west,north,east")
    return tuple(parts)  # type: ignore[return-value]


def main() -> int:
    _fix_windows_console_encoding()
    p = argparse.ArgumentParser()
    p.add_argument("--level", type=int, required=True, choices=[3, 5])
    p.add_argument("--bbox", type=parse_bbox, action="append", default=None,
                    help="Required for --level 5 (Trap 4). Repeatable. Format: south,west,north,east. "
                         "e.g. --bbox 11.2,75.7,12.0,76.5 --bbox 19.3,72.5,20.1,73.3")
    p.add_argument("--batch-size", type=int, default=500)
    args = p.parse_args()

    if args.level == 5 and not args.bbox:
        print(
            "REFUSING: --level 5 requires --bbox. Loading ADM5 nationwide is "
            "649,771 polygons (~1GB) and will blow Neon's 0.5GB free tier (Trap 4, §4.1). "
            "geoBoundaries' gbOpen ADM5 files carry no state attribute to filter on "
            "(confirmed by inspection — see this file's module docstring), so scope by "
            "bounding box instead, e.g. --bbox 11.2,75.7,12.0,76.5 for Wayanad.",
            file=sys.stderr,
        )
        return 1

    path = f"data/raw/ind_adm{args.level}.geojson"
    if not os.path.exists(path):
        print(f"REFUSING: {path} does not exist. Run scripts/fetch_data.sh first.", file=sys.stderr)
        return 1

    load(path, args.level, args.bbox, args.batch_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
