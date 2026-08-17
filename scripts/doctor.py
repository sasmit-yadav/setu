#!/usr/bin/env python
"""scripts/doctor.py — what can this laptop actually do?

Prints a capability report. NEVER fails the build; its whole job is to make
"works on my machine" impossible to say by accident. Run it on all six laptops
and paste the output in the team channel.

The design rule, borrowed from PRAVESH: report what this machine can run, never
guess and never silently skip. An absent capability degrades a NAMED feature
honestly — it never makes the platform pretend.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import shutil
import socket
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent.parent


def has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def has_bin(name: str) -> bool:
    return shutil.which(name) is not None


def env(name: str) -> bool:
    v = os.environ.get(name, "").strip()
    # A placeholder from .env.example is NOT a configured value. Saying otherwise
    # is exactly the kind of quiet lie this whole project exists to avoid.
    return bool(v) and not v.startswith(("generate-", "xkeysib-xxx", "ACxxxx", "xxxx"))


def tcp(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def docker_daemon() -> bool:
    if not has_bin("docker"):
        return False
    try:
        return subprocess.run(
            ["docker", "info"], capture_output=True, timeout=15
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


SECTIONS: list[tuple[str, list[tuple[str, bool, str]]]] = [
    ("toolchain", [
        ("python 3.11 or 3.12", (3, 11) <= sys.version_info[:2] <= (3, 12),
         "3.13/3.14 have no wheels for asyncpg, lxml, rasterio, lightgbm"),
        ("git", has_bin("git"), "required"),
        ("node + npm", has_bin("npm"), "both frontends"),
        ("docker cli", has_bin("docker"), "local infra"),
        ("docker daemon running", docker_daemon(), "start Docker Desktop"),
    ]),
    ("local services", [
        # Port 5433, NOT 5432 — this machine has a native Windows postgres.exe
        # already bound to 5432 (found the hard way on Day 6: TCP connections
        # to "localhost:5432" were silently authenticating against THAT
        # service, with a different password, and neither side logged
        # anything to explain why). infra/docker-compose.yml publishes the
        # container on 5433 specifically to avoid this — checking 5432 here
        # would report the native service as "our" database.
        ("setu-db reachable :5433", tcp("localhost", 5433), "python run.py db-up"),
        ("redis reachable :6379", tcp("localhost", 6379), "python run.py db-up"),
    ]),
    ("database config (Part 23: two urls, not one)", [
        ("DATABASE_URL_POOLED", env("DATABASE_URL_POOLED"), "app runtime"),
        ("DATABASE_URL_DIRECT", env("DATABASE_URL_DIRECT"), "migrations only"),
    ]),
    ("secrets — absence is a HARD stop for the named feature", [
        ("PHONE_HASH_PEPPER", env("PHONE_HASH_PEPPER"),
         "migration 0012 FAILS LOUDLY without it (Trap 11)"),
        ("ALERT_SIGNING_SEED_B64", env("ALERT_SIGNING_SEED_B64"),
         "B10 peer relay cannot sign (Rule 11)"),
        ("JWT_SIGNING_SECRET", env("JWT_SIGNING_SECRET"), "auth"),
        ("WEBHOOK_HMAC_SECRET", env("WEBHOOK_HMAC_SECRET"), "provider callbacks"),
    ]),
    ("channels", [
        ("FCM_SERVICE_ACCOUNT_JSON", env("FCM_SERVICE_ACCOUNT_JSON"),
         "push — the PRIMARY channel (Trap 5)"),
        ("  ^ file actually exists",
         (ROOT / os.environ.get("FCM_SERVICE_ACCOUNT_JSON", "nope")).exists()
         if os.environ.get("FCM_SERVICE_ACCOUNT_JSON") else False,
         "download it from Firebase > Service accounts"),
        ("TWILIO_ACCOUNT_SID", env("TWILIO_ACCOUNT_SID"), "SMS + IVR + human relay"),
        ("TWILIO_AUTH_TOKEN", env("TWILIO_AUTH_TOKEN"), "same"),
        ("BREVO_API_KEY", env("BREVO_API_KEY"), "email escalation step"),
    ]),
    ("optional — absence degrades a named feature honestly", [
        ("OPENCELLID_TOKEN", env("OPENCELLID_TOKEN"),
         "OPTIONAL — Part 30's 5-feature fallback applies, D8f reports 'unknown'"),
        ("SLACK_OR_DISCORD_ALERT_WEBHOOK", env("SLACK_OR_DISCORD_ALERT_WEBHOOK"),
         "all of Part 28's monitoring has nowhere to go without it"),
        ("HF_SPACE_URL", env("HF_SPACE_URL"), "translation + dedup embeddings (Part 22)"),
    ]),
    ("python packages", [
        ("alembic", has_module("alembic"), "migrations"),
        ("asyncpg", has_module("asyncpg"), "runtime db"),
        ("nacl (signing)", has_module("nacl"), "REQUIRED on the api service"),
        ("torch — ML service ONLY", has_module("torch"),
         "absent here is CORRECT (Part 22). Installing it re-creates the 512 MB OOM."),
    ]),
    ("offline demo assets", [
        ("basemap .pmtiles present",
         (ROOT / "web/console/public/tiles/setu-basemap.pmtiles").exists(),
         "WITHOUT IT THE MAP IS BLANK OFFLINE at 4:45 in the script (§1.6.5)"),
        ("a committed snapshot exists",
         any((ROOT / "data" / "snapshots").glob("*.json"))
         if (ROOT / "data" / "snapshots").exists() else False,
         "python run.py snapshot — the demo runs from this"),
    ]),
]


def main() -> int:
    width = max(len(n) for _, checks in SECTIONS for n, _, _ in checks)
    print("\nSETU doctor — what this machine can run")
    for title, checks in SECTIONS:
        print(f"\n  {title}")
        print("  " + "─" * (width + 8))
        for name, ok, note in checks:
            mark = "OK  " if ok else "--  "
            trailer = "" if ok else f"  <- {note}"
            print(f"  {mark}{name:<{width}}{trailer}")
    print(
        "\n  Nothing above is required for the whole system to run. Absent"
        "\n  capabilities degrade NAMED features honestly — they never make the"
        "\n  platform guess.\n"
    )
    return 0  # deliberately never non-zero: this is a report, not a gate


if __name__ == "__main__":
    sys.exit(main())
