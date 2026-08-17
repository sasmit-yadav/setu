#!/usr/bin/env python
"""scripts/load_safe_zones.py — §4.6. Shelters/schools/hospitals from OSM
Overpass into safe_zone. Scoped to a bounding box (not "area=IN") because a
nationwide Overpass query is exactly the kind of request their documented
courtesy limits (10K queries/day, 1GB/day) are meant to prevent one script
from blowing through in a single run — the two case-study districts' bboxes
are what the demo actually needs.

Usage:
    python scripts/load_safe_zones.py --bbox 11.4,75.9,11.8,76.3 --name wayanad
    python scripts/load_safe_zones.py --bbox 19.5,72.6,19.9,73.1 --name palghar
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx
import psycopg

USER_AGENT = "SETU-disaster-alert-platform (build-time safe-zone loader; contact via repo)"

# The main overpass-api.de instance the design spec names (§4.6) is public,
# free, and occasionally 504s under load — observed directly while building
# this loader. Retrying with backoff, then falling through to a mirror,
# rather than treating one timeout as "the source is down."
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


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


def overpass_query(bbox: tuple[float, float, float, float]) -> str:
    s, w, n, e = bbox
    return f"""
    [out:json][timeout:25];
    (
      node["amenity"~"school|community_centre|hospital"]({s},{w},{n},{e});
      node["emergency"="shelter"]({s},{w},{n},{e});
      node["building"="government"]["amenity"="townhall"]({s},{w},{n},{e});
    );
    out center;
    """


def kind_of(tags: dict) -> str:
    if tags.get("emergency") == "shelter":
        return "shelter"
    amenity = tags.get("amenity", "")
    if amenity in ("school", "community_centre", "hospital"):
        return amenity if amenity != "community_centre" else "community_centre"
    if tags.get("building") == "government":
        return "townhall"
    return "other"


def main() -> int:
    _fix_windows_console_encoding()
    p = argparse.ArgumentParser()
    p.add_argument("--bbox", required=True, help="south,west,north,east")
    p.add_argument("--name", required=True, help="label for logging only")
    args = p.parse_args()

    bbox = tuple(float(x) for x in args.bbox.split(","))
    query = overpass_query(bbox)

    r = None
    last_err: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(2):
            try:
                r = httpx.post(
                    endpoint, data={"data": query},
                    headers={"User-Agent": USER_AGENT}, timeout=45.0,
                )
                r.raise_for_status()
                last_err = None
                break
            except httpx.HTTPStatusError as e:
                last_err = e
                print(f"  {endpoint} attempt {attempt + 1} failed ({e.response.status_code}), retrying...")
                time.sleep(5)
        if last_err is None:
            break
    if last_err is not None:
        raise last_err

    elements = r.json().get("elements", [])
    print(f"  {args.name}: {len(elements)} elements from Overpass")

    conn = psycopg.connect(db_url())
    inserted = 0
    with conn.cursor() as cur:
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name")
            kind = kind_of(tags)
            lon, lat = el.get("lon"), el.get("lat")
            if lon is None or lat is None:
                continue
            cur.execute(
                """
                INSERT INTO safe_zone (name, kind, geom, source_id, fetched_at)
                VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                        'osm_overpass', now())
                """,
                (name, kind, lon, lat),
            )
            inserted += 1
    conn.commit()
    conn.close()
    print(f"  DONE: {inserted} safe_zone rows inserted for {args.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
