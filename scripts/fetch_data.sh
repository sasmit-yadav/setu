#!/usr/bin/env bash
# scripts/fetch_data.sh — build-time geospatial downloads (§1.6.2), with the
# URL corrections scripts/verify_data_sources.py found and confirmed live.
#
# Two real bugs fixed here relative to the design spec's literal script:
#
#   1. geoBoundaries files are Git-LFS-tracked. raw.githubusercontent.com
#      returns the ~130-byte LFS POINTER TEXT, not the actual geometry.
#      Fixed: use media.githubusercontent.com/media/<path> instead.
#
#   2. The Copernicus DEM bucket (copernicus-dem-30m) names every key
#      "Copernicus_DSM_COG_10_{tile}_DEM", not "..._COG_30_...". The spec's
#      key naming would 404 on all four tiles and wrongly trigger the SRTM
#      fallback for a source that is actually fully present.
#
# WorldPop's exact filename in the spec was independently confirmed correct
# (489MB real TIFF) — not touched here.
#
# Run from the repo root: bash scripts/fetch_data.sh
set -euo pipefail

mkdir -p data/raw data/raw/dem

echo "== 1. ADMIN BOUNDARIES — geoBoundaries gbOpen, ODbL 1.0, no auth =="
echo "   (LFS-backed — using media.githubusercontent.com, NOT raw.githubusercontent.com)"

GB_MEDIA="https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/IND"

curl -fSL -o data/raw/ind_adm3.geojson \
  "$GB_MEDIA/ADM3/geoBoundaries-IND-ADM3_simplified.geojson"

curl -fSL -o data/raw/ind_adm5.geojson \
  "$GB_MEDIA/ADM5/geoBoundaries-IND-ADM5_simplified.geojson"

# Sanity check: refuse to proceed if either file is suspiciously small — this
# is exactly the failure mode the LFS-pointer bug produces silently otherwise.
for f in data/raw/ind_adm3.geojson data/raw/ind_adm5.geojson; do
  size=$(wc -c < "$f")
  if [ "$size" -lt 1000000 ]; then
    echo "FATAL: $f is only $size bytes — this looks like an LFS pointer, not real geometry." >&2
    head -c 200 "$f" >&2
    exit 1
  fi
  echo "  OK: $f ($size bytes)"
done

echo
echo "== 2. POPULATION — WorldPop constrained 100m, CC BY 4.0, no auth =="
curl -fSL -o data/raw/ind_pop.tif \
  "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/IND/ind_ppp_2020_UNadj_constrained.tif"
echo "  OK: data/raw/ind_pop.tif ($(wc -c < data/raw/ind_pop.tif) bytes)"

echo
echo "== 3. TERRAIN — Copernicus GLO-30, the 4 Wayanad/Palghar tiles =="
echo "   (key naming is COG_10, not COG_30 as the spec's own script assumed)"
for tile in N11_00_E076_00 N19_00_E072_00 N19_00_E073_00 N11_00_E077_00; do
  url="https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_${tile}_DEM/Copernicus_DSM_COG_10_${tile}_DEM.tif"
  if curl -fSL -o "data/raw/dem/${tile}.tif" "$url"; then
    echo "  OK: $tile"
  else
    echo "  MISSING: $tile — SRTM fallback needed for this cell only (Part 29)"
  fi
done

echo
echo "== 4. BUILDINGS — Google Open Buildings =="
echo "   [RECONFIRM] per-S2-cell CSV URLs cannot be resolved generically —"
echo "   run scripts/load_buildings.py --district wayanad --district palghar"
echo "   (not yet written) once S2 cell IDs for those two districts are computed."

echo
echo "== 5. CELL TOWERS — OpenCelliD, requires \$OPENCELLID_TOKEN =="
if [ -z "${OPENCELLID_TOKEN:-}" ]; then
  echo "  SKIPPED: OPENCELLID_TOKEN not set. Part 30's 5-feature fallback applies."
else
  for mcc in 404 405; do
    curl -fSL -o "data/raw/cells_${mcc}.csv.gz" \
      "https://opencellid.org/ocid/downloads?token=${OPENCELLID_TOKEN}&type=mcc&file=${mcc}.csv.gz"
    echo "  OK: mcc=$mcc"
  done
fi

echo
echo "== 6. BASEMAP — Protomaps PMTiles =="
echo "   [RECONFIRM] exact current build filename at build.protomaps.com —"
echo "   the date-stamped build path must be checked at load time, not hardcoded."
echo "   Not fetched automatically here; see docs/SETU_MASTER_v3.0_MERGED.md §1.6.5."

echo
echo "Done. Run scripts/verify_data_sources.py again any time to re-confirm liveness."
