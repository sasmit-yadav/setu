#!/usr/bin/env python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], label: str, *, optional: bool = False) -> int:
    print(f"\n=== {label} ===")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        if optional:
            print(f"  skipped ({label})")
            return 0
        print(f"FAILED at {label}", file=sys.stderr)
    return result.returncode


def main() -> int:
    steps: list[tuple[list[str], str, bool]] = [
        (["docker", "compose", "-f", "infra/docker-compose.yml", "up", "-d"], "docker_up", False),
        ([sys.executable, "scripts/wait_for_db.py"], "wait_db", False),
        ([sys.executable, "-m", "alembic", "upgrade", "head"], "migrate", False),
        ([sys.executable, "scripts/upsert_app_config.py"], "app_config", False),
        ([sys.executable, "scripts/import_enrollment_csv.py"], "enrollment_csv", True),
        ([sys.executable, "scripts/verify_data_layer.py"], "verify", False),
    ]
    for cmd, label, optional in steps:
        if run(cmd, label, optional=optional) != 0:
            return 1
    print("\nLocal data bootstrap complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
