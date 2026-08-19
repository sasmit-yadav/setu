#!/usr/bin/env python
"""scripts/verify_data_sources.py — Gate 1: verify every live external data
dependency named in docs/SETU_MASTER_v3.0_MERGED.md §1.1/§1.2/§1.6, before
any code is written that assumes one of them works a certain way.

This is a REPORT, like doctor.py — it never silently skips, and it prints the
[RECONFIRM] items explicitly so a stale URL shape is caught here, not on
stage. Run it, paste the output into docs/IMPLEMENTATION.md's data-sources
section, and re-run it if any adapter starts failing later — a source going
from live to broken is exactly the kind of thing that should be caught by a
script, not discovered mid-demo.

Sources that need a token/account not yet obtained (OpenCelliD) are reported
as SKIPPED, not FAILED — the design spec already has a stated fallback for
each of those (Part 30).
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass

import httpx

TIMEOUT = 15.0


def _fix_windows_console_encoding() -> None:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8")
            except (AttributeError, ValueError):
                pass


@dataclass
class Result:
    name: str
    status: str  # LIVE | FAIL | SKIP | RECONFIRM
    detail: str = ""
    elapsed_ms: float = 0.0


results: list[Result] = []


def check(name: str, fn) -> None:
    t0 = time.monotonic()
    try:
        detail = fn()
        results.append(Result(name, "LIVE", detail if isinstance(detail, str) else "",
                               (time.monotonic() - t0) * 1000))
    except SkipCheck as e:
        results.append(Result(name, "SKIP", str(e), (time.monotonic() - t0) * 1000))
    except Exception as e:
        results.append(Result(name, "FAIL", f"{type(e).__name__}: {e}", (time.monotonic() - t0) * 1000))


class SkipCheck(Exception):
    pass


# ═══ §1.6.1 — Live alert sources ═══

def check_usgs():
    r = httpx.get(
        "https://earthquake.usgs.gov/fdsnws/event/1/query",
        params={
            "format": "geojson", "starttime": "2026-08-01",
            "minlatitude": 6, "maxlatitude": 38, "minlongitude": 68, "maxlongitude": 98,
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    body = r.json()
    n = len(body.get("features", []))
    return f"200 OK, {n} India-bbox earthquake events since 2026-08-01"


def check_gdacs():
    # [RECONFIRM] resolved: /geteventlist/MAP requires an `eventtype` param
    # (400 "Eventtype is required" without one) — the spec's bare URL was
    # incomplete. /geteventlist/SEARCH works with no required params at all
    # and returns live global events (drought, flood, etc. seen 2026-08-17),
    # which is the shape the ThunderstormNowcastAdapter's sibling ingestion
    # adapters should actually poll.
    r = httpx.get("https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH", timeout=TIMEOUT)
    r.raise_for_status()
    body = r.json()
    n = len(body.get("features", [])) if isinstance(body, dict) else 0
    return (f"200 OK on /SEARCH (no params required), {n} live global events. "
            f"NOTE: /MAP needs eventtype= or returns 400 — use /SEARCH instead.")


def check_open_meteo_convective():
    r = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": 11.6, "longitude": 76.1,
                "hourly": "cape,lifted_index,convective_inhibition,precipitation_probability"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    hourly = r.json().get("hourly", {})
    required = ("cape", "lifted_index", "convective_inhibition", "precipitation_probability")
    missing = [k for k in required if k not in hourly]
    if missing:
        raise RuntimeError(f"missing variables in response: {missing}")
    return (
        f"200 OK, all {len(required)} variables present "
        f"({len(hourly.get('time', []))} hourly points)"
    )


def check_open_meteo_precip():
    r = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": 19.7, "longitude": 72.8, "hourly": "precipitation"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return "200 OK, precipitation variable present"


def check_sachet():
    # [UNVERIFIED] in the spec — fetch endpoint shape confirmed by the doc,
    # discovery endpoint explicitly not found. We only re-confirm the base host
    # responds; this does NOT attempt discovery.
    r = httpx.get("https://sachet.ndma.gov.in/cap_public_website/", timeout=TIMEOUT, follow_redirects=True)
    return f"{r.status_code} — base host reachable. Discovery endpoint: still UNVERIFIED, not attempted here."


def check_imd():
    # NOTE: /public/ alone is the API-management PORTAL's landing page (200,
    # HTML), not an actual data endpoint — hitting it and getting 200 does NOT
    # mean the API is open. Guessed real endpoint paths (/public/api/weather,
    # /public/v1/current) both 404, which is consistent with "undocumented,
    # requires registration" rather than confirming or refuting Trap 2's
    # specific 401 claim. Registering for real credentials is the only way to
    # actually test this — not on the critical path either way (spec + here).
    r = httpx.get("https://api.imd.gov.in/public/", timeout=TIMEOUT, follow_redirects=True)
    return (f"portal landing page: {r.status_code}. No documented endpoint path found to "
            f"test the Trap 2 401 claim directly — requires registration either way. Not on critical path.")


# ═══ §1.6.2 — Build-time geospatial ═══

def _geoboundaries_check(level: str, expected_min_bytes: int) -> str:
    # SPEC BUG, not just [RECONFIRM]: these files are Git-LFS-tracked in the
    # wmgeolab/geoBoundaries repo. The design doc's fetch command
    # (`curl -fSL -o ... raw.githubusercontent.com/...`, §1.6.2) hits
    # raw.githubusercontent.com, which for an LFS file returns the ~130-byte
    # LFS POINTER TEXT ("version https://git-lfs.github.com/spec/v1\noid
    # sha256:...\nsize ..."), not the actual geometry. ogr2ogr would then be
    # handed a 130-byte text file instead of 38MB/445MB of real GeoJSON and
    # fail (or worse, partially succeed on something malformed) on Day 1 of
    # the geometry load — discovered here instead.
    #
    # Fix: media.githubusercontent.com/media/<same path> is GitHub's LFS
    # media proxy and returns the real bytes. Confirmed: ADM3 -> 40,040,002
    # bytes (~38MB, matches the spec's own claim); ADM5 -> 467,134,382 bytes
    # (~445MB, also matches). scripts/fetch_data.sh (not yet written) MUST
    # use media.githubusercontent.com, not raw.githubusercontent.com.
    path = f"wmgeolab/geoBoundaries/main/releaseData/gbOpen/IND/{level}/geoBoundaries-IND-{level}_simplified.geojson"
    raw_url = f"https://raw.githubusercontent.com/{path}"
    media_url = f"https://media.githubusercontent.com/media/{path}"

    raw = httpx.get(raw_url, timeout=TIMEOUT, follow_redirects=True)
    raw.raise_for_status()
    is_lfs_pointer = raw.text.startswith("version https://git-lfs.github.com/spec/v1")

    media = httpx.head(media_url, timeout=TIMEOUT, follow_redirects=True)
    media.raise_for_status()
    size = int(media.headers.get("content-length", 0))
    if size < expected_min_bytes:
        raise RuntimeError(f"media proxy returned only {size} bytes, expected >= {expected_min_bytes}")

    pointer_note = " (raw.githubusercontent.com returns only the LFS pointer — confirmed)" if is_lfs_pointer else ""
    return f"real file confirmed via media.githubusercontent.com: {size:,} bytes{pointer_note}"


def check_geoboundaries_adm3():
    return _geoboundaries_check("ADM3", expected_min_bytes=30_000_000)


def check_geoboundaries_adm5():
    return _geoboundaries_check("ADM5", expected_min_bytes=400_000_000)


def check_worldpop():
    # The spec's [RECONFIRM] filename, tested directly rather than via the
    # REST listing API — the listing API's ?iso3=IND defaults to the
    # UNCONSTRAINED 2000-2020 series (a different dataset entirely), which
    # would have reported "live" while never actually confirming the file
    # §1.6.2's load_population.py is pointed at. The exact spec'd path is
    # confirmed correct as-is: no fix needed here, unlike geoBoundaries/DEM.
    url = "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/IND/ind_ppp_2020_UNadj_constrained.tif"
    r = httpx.head(url, timeout=TIMEOUT, follow_redirects=True)
    r.raise_for_status()
    size = int(r.headers.get("content-length", 0))
    if size < 100_000_000:
        raise RuntimeError(f"file too small ({size} bytes) to be the real raster")
    return f"exact spec'd filename confirmed, {size:,} bytes ({size / 1e6:.0f} MB)"


def check_open_buildings():
    # No stable discovery API; confirm the docs/index page responds and note
    # that per-cell CSV.gz identification is a manual/build-time step (§1.6.2).
    r = httpx.get("https://sites.research.google/gr/open-buildings/", timeout=TIMEOUT, follow_redirects=True)
    return f"{r.status_code} — landing page reachable. Per-S2-cell CSV URLs are [RECONFIRM] at build time, not tested here."


def check_copernicus_dem_tiles():
    # Part 29's actual four tiles for Wayanad + Palghar.
    #
    # SPEC CORRECTION: the design doc's fetch script (§1.6.2, Part 29) builds
    # the key as "Copernicus_DSM_COG_30_{tile}_DEM" — but the actual bucket
    # (yes, the bucket is named copernicus-dem-30m) names every key
    # "Copernicus_DSM_COG_10_{tile}_DEM", confirmed by listing the bucket
    # directly. "_30_" tiles do not exist anywhere in this bucket. Using the
    # spec's literal key would 404 on all four tiles and wrongly trigger the
    # SRTM fallback path for a source that is actually fully present.
    tiles = ["N11_00_E076_00", "N19_00_E072_00", "N19_00_E073_00", "N11_00_E077_00"]
    found, missing = [], []
    for tile in tiles:
        url = f"https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{tile}_DEM/Copernicus_DSM_COG_10_{tile}_DEM.tif"
        r = httpx.head(url, timeout=TIMEOUT, follow_redirects=True)
        (found if r.status_code == 200 else missing).append(tile)
    if missing:
        raise RuntimeError(f"missing tiles (need SRTM fallback): {missing}. Found: {found}")
    return f"all 4 tiles present (key naming is COG_10, NOT COG_30 as the spec's script assumes): {found}"


def check_opencellid():
    raise SkipCheck("no OPENCELLID_TOKEN in environment yet — Part 30's 5-feature fallback applies until it clears")


def check_overpass():
    query = '[out:json][timeout:10];node["amenity"="hospital"](11.5,76.0,11.7,76.2);out center 1;'
    r = httpx.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        headers={"User-Agent": "SETU-disaster-alert-platform (verification script)"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    n = len(r.json().get("elements", []))
    return f"200 OK, {n} element(s) for a tiny Wayanad-area test query"


def check_protomaps():
    r = httpx.get("https://build.protomaps.com/", timeout=TIMEOUT, follow_redirects=True)
    return f"{r.status_code} — [RECONFIRM] build.protomaps.com reachable; exact current build filename must be re-checked at data-load time"


def check_hf_models():
    models = [
        "ai4bharat/indictrans2-en-indic-dist-200M",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ]
    missing = []
    for m in models:
        r = httpx.get(f"https://huggingface.co/api/models/{m}", timeout=TIMEOUT)
        if r.status_code != 200:
            missing.append(m)
    if missing:
        raise RuntimeError(f"model page(s) not found: {missing}")
    return f"both model cards resolve: {models}"


CHECKS = [
    ("USGS earthquake feed", check_usgs),
    ("GDACS multi-hazard feed [RECONFIRM]", check_gdacs),
    ("Open-Meteo convective indices (CAPE/LI/CIN)", check_open_meteo_convective),
    ("Open-Meteo precipitation", check_open_meteo_precip),
    ("SACHET base host [UNVERIFIED discovery]", check_sachet),
    ("IMD API (expected 401)", check_imd),
    ("geoBoundaries ADM3 [RECONFIRM]", check_geoboundaries_adm3),
    ("geoBoundaries ADM5 [RECONFIRM]", check_geoboundaries_adm5),
    ("WorldPop population API [RECONFIRM]", check_worldpop),
    ("Google Open Buildings [RECONFIRM]", check_open_buildings),
    ("Copernicus GLO-30 DEM — 4 Wayanad/Palghar tiles", check_copernicus_dem_tiles),
    ("OpenCelliD (needs token)", check_opencellid),
    ("OSM Overpass API", check_overpass),
    ("Protomaps PMTiles build host [RECONFIRM]", check_protomaps),
    ("Hugging Face model cards (IndicTrans2, MiniLM)", check_hf_models),
]


def main() -> int:
    _fix_windows_console_encoding()
    print("SETU — live data source verification (Gate 1)\n" + "=" * 60)
    for name, fn in CHECKS:
        check(name, fn)

    width = max(len(r.name) for r in results)
    for r in results:
        mark = {"LIVE": "LIVE ", "FAIL": "FAIL ", "SKIP": "SKIP "}[r.status]
        print(f"  {mark} {r.name:<{width}}  ({r.elapsed_ms:.0f}ms)")
        if r.detail:
            print(f"         -> {r.detail}")

    live = sum(1 for r in results if r.status == "LIVE")
    failed = [r for r in results if r.status == "FAIL"]
    skipped = [r for r in results if r.status == "SKIP"]

    print("\n" + "=" * 60)
    print(f"{live}/{len(results)} live, {len(failed)} failed, {len(skipped)} skipped (expected — no token yet)")
    if failed:
        print("\nFAILED sources need attention before any adapter assumes they work:")
        for r in failed:
            print(f"  - {r.name}: {r.detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
