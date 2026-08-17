#!/usr/bin/env python
"""scripts/run_geometry_pipeline.py — orchestrates the full geometry load in
the correct order, so nobody has to remember the sequence (admin units must
exist before population/terrain zonal stats can run against them, and
relay_nodes.sql needs admin_unit rows to exist before it can seed anything).

    python scripts/run_geometry_pipeline.py

Idempotency note: load_admin_units.py dedupes on lgd_code where present, but
geoBoundaries rows with a NULL lgd_code will duplicate on a second run of
this pipeline. Safe to run once on a fresh database; not yet safe to re-run
against a populated one without a TRUNCATE first. Tracked in TASK.md.
"""

from __future__ import annotations

import subprocess
import sys

STEPS = [
    ("Load ADM3 nationwide", [sys.executable, "scripts/load_admin_units.py", "--level", "3"]),
    ("Load ADM5 for Wayanad + Palghar (Trap 4 — bbox-scoped, "
     "geoBoundaries ADM5 has no state attribute to filter on)",
     [sys.executable, "scripts/load_admin_units.py", "--level", "5",
      "--bbox", "11.2,75.7,12.0,76.5", "--bbox", "19.3,72.5,20.1,73.3"]),
    ("Zonal population, level 3", [sys.executable, "scripts/load_population.py", "--level", "3"]),
    ("Zonal population, level 5", [sys.executable, "scripts/load_population.py", "--level", "5"]),
    ("Terrain ruggedness (all levels)", [sys.executable, "scripts/load_terrain.py"]),
    ("Safe zones — Wayanad", [sys.executable, "scripts/load_safe_zones.py",
                              "--bbox", "11.4,75.9,11.8,76.3", "--name", "wayanad"]),
    ("Safe zones — Palghar", [sys.executable, "scripts/load_safe_zones.py",
                              "--bbox", "19.5,72.6,19.9,73.1", "--name", "palghar"]),
    ("Re-seed relay_nodes.sql (needs admin_unit rows to exist)", None),  # handled specially below
]


def main() -> int:
    for label, cmd in STEPS:
        print(f"\n=== {label} ===")
        if cmd is None:
            print("  (run manually: see the note in data/seeds/05_relay_nodes.sql — "
                  "still needs REAL phone numbers before it's demo-ready, not just admin_unit rows)")
            continue
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"FAILED at: {label}", file=sys.stderr)
            return 1
    print("\nDone. Check: SELECT level, COUNT(*) FROM admin_unit GROUP BY level;")
    return 0


if __name__ == "__main__":
    sys.exit(main())
