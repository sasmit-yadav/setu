# Four-tile DEM check — 21 Aug 2026

Part 19: *"The four-tile DEM check has a committed, dated pass/fail log."*
Part 29 names this exact check: `terrain_ruggedness` depends on exactly two
case-study districts (Wayanad, Palghar), whose centroids sit near four
candidate 1°×1° Copernicus GLO-30 tiles.

**Run with the AWS CLI, `--no-sign-request`, against the real S3 bucket** —
not simulated:

```bash
for tile in N11_00_E076_00 N19_00_E072_00 N19_00_E073_00 N11_00_E077_00; do
  aws s3 ls --no-sign-request \
    "s3://copernicus-dem-30m/Copernicus_DSM_COG_10_${tile}_DEM/" \
    && echo "OK: $tile" || echo "MISSING: $tile"
done
```

**One correction to Part 29's own literal command:** it writes the key as
`Copernicus_DSM_COG_30_{tile}_DEM`. The bucket is genuinely named
`copernicus-dem-30m`, but every object inside it uses `COG_10` in the key —
confirmed here by listing, and already recorded independently in
`docs/IMPLEMENTATION.md`'s "Copernicus DEM tile keys are named `COG_10`, not
`COG_30`" note and used correctly in `scripts/fetch_data.sh`. Running Part 29's
literal command as written returns nothing and would be misread as all four
tiles missing, when they are all present.

## Result

| Tile | Covers | Status | `.tif` size |
|---|---|---|---|
| `N11_00_E076_00` | Wayanad (≈11.6°N, 76.1°E) | ✅ OK | 44,177,013 bytes |
| `N19_00_E072_00` | Palghar (≈19.7°N, 72.8°E) | ✅ OK | 13,336,459 bytes |
| `N19_00_E073_00` | Palghar's eastern neighbour cell | ✅ OK | 45,865,641 bytes |
| `N11_00_E077_00` | Wayanad's eastern neighbour cell | ✅ OK | 42,605,112 bytes |

**4/4 tiles present. No SRTM fallback needed for either case-study district.**
Every listing returned the real object (`Copernicus_DSM_COG_10_{tile}_DEM.tif`)
plus its `AUXFILES/`, `INFO/`, `PREVIEW/` sub-prefixes and companion `.xml` —
confirming these are genuine data objects, not empty placeholder prefixes.

## What this means downstream

`unit_features.terrain_ruggedness` and `mean_elevation_m` for Wayanad and
Palghar can be computed entirely from Copernicus GLO-30, with no per-cell SRTM
mixing required. If a future run against a different district set finds a
missing tile, mixing sources per-cell is still fine per Part 29 — ruggedness is
computed per admin-unit centroid, and each centroid falls in exactly one cell.
