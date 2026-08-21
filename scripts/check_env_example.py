#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENV_EXAMPLE = ROOT / ".env.example"

REQUIRED_KEYS = {
    "DATABASE_URL_POOLED",
    "DATABASE_URL_DIRECT",
    "DB_POOL_SIZE",
    "DB_POOL_MAX_OVERFLOW",
    "DB_POOL_TIMEOUT_S",
    "REDIS_URL",
    "REDIS_NAMESPACE",
    "FCM_SERVICE_ACCOUNT_JSON",
    "FIREBASE_API_KEY",
    "FIREBASE_PROJECT_ID",
    "FIREBASE_MESSAGING_SENDER_ID",
    "FIREBASE_APP_ID",
    "FIREBASE_VAPID_PUBLIC_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_WEBHOOK_AUTH_TOKEN",
    "TWILIO_FROM_NUMBER",
    "BREVO_API_KEY",
    "PHONE_HASH_PEPPER",
    "PGCRYPTO_SYM_KEY",
    "ALERT_SIGNING_SEED_B64",
    "HF_SPACE_URL",
    "INTERNAL_ML_KEY",
    "SETU_LOAD_ML_MODELS",
    "SETU_TRANSLATE_HF_ID",
    "SETU_EMBED_HF_ID",
    "JWT_SIGNING_SECRET",
    "WEBHOOK_HMAC_SECRET",
    "SENTRY_DSN",
    "SENTRY_ENABLED",
    "OPENCELLID_TOKEN",
    "PUBLIC_BASE_URL",
    "SLACK_OR_DISCORD_ALERT_WEBHOOK",
    "SETU_DEMO_PASSWORD",
}


def parse_keys(path: pathlib.Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if re.match(r"^[A-Z0-9_]+$", key):
            keys.add(key)
    return keys


def main() -> int:
    if not ENV_EXAMPLE.exists():
        print(f"missing {ENV_EXAMPLE}")
        return 1
    present = parse_keys(ENV_EXAMPLE)
    missing = sorted(REQUIRED_KEYS - present)
    extra = sorted(present - REQUIRED_KEYS)
    ok = True
    if missing:
        ok = False
        for key in missing:
            print(f"missing from .env.example: {key}")
    if extra:
        for key in extra:
            print(f"extra in .env.example (not in Part 25 list): {key}")
    if ok:
        print("check_env_example: clean")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
