#!/usr/bin/env python
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEON_ENV = ROOT / ".env.neon"
sys.path.insert(0, str(ROOT))

from scripts.env_loader import load_env_file


def neon_env() -> dict[str, str]:
    if not NEON_ENV.exists():
        print(f"Missing {NEON_ENV}", file=sys.stderr)
        sys.exit(1)
    merged = os.environ.copy()
    load_env_file(NEON_ENV, override=False)
    for key, value in os.environ.items():
        if key.startswith("DATABASE_") or key in {"PHONE_HASH_PEPPER", "PGCRYPTO_SYM_KEY"}:
            merged[key] = value
    load_env_file(NEON_ENV, override=True)
    for key, value in os.environ.items():
        merged[key] = value
    if not merged.get("DATABASE_URL_DIRECT"):
        print("DATABASE_URL_DIRECT missing from .env.neon", file=sys.stderr)
        sys.exit(1)
    return merged


def run_step(env: dict[str, str], cmd: list[str], label: str) -> int:
    print(f"\n=== {label} ===")
    result = subprocess.run(cmd, cwd=ROOT, env=env)
    if result.returncode != 0:
        print(f"FAILED at {label}", file=sys.stderr)
    return result.returncode


def main() -> int:
    env = neon_env()
    target = env["DATABASE_URL_DIRECT"].split("@")[-1]
    print(f"Neon bootstrap -> {target}")
    local_env = ROOT / ".env"
    if local_env.exists():
        load_env_file(local_env, override=False)
        for key in ("PHONE_HASH_PEPPER", "PGCRYPTO_SYM_KEY", "ALERT_SIGNING_SEED_B64"):
            if os.environ.get(key):
                env[key] = os.environ[key]
    steps = [
        ([sys.executable, "-m", "alembic", "upgrade", "head"], "migrate"),
        ([sys.executable, "scripts/upsert_app_config.py"], "app_config"),
        ([sys.executable, "scripts/push_geometry_to_neon.py"], "geometry"),
        ([sys.executable, "scripts/provision_demo_accounts.py"], "provision_demo"),
    ]
    for cmd, label in steps:
        code = run_step(env, cmd, label)
        if code != 0:
            return code
    env["SETU_ENV_FILE"] = str(NEON_ENV)
    code = run_step(env, [sys.executable, "scripts/verify_data_layer.py"], "verify")
    return code


if __name__ == "__main__":
    sys.exit(main())
