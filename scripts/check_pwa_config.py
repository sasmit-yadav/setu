#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CITIZEN_SRC = ROOT / "web" / "citizen" / "src"

FORBIDDEN = [
    (re.compile(r"useState\s*\(\s*280\s*\)"), "hardcoded free_text_max before config load"),
    (re.compile(r"networkTimeoutSeconds:\s*\d+"), "hardcoded pwa.network_timeout_seconds fallback"),
    (re.compile(r"alertCacheMaxAgeSeconds:\s*\d+"), "hardcoded pwa.alert_cache_max_age_seconds fallback"),
    (re.compile(r"ackRetentionMinutes:\s*\d+"), "hardcoded pwa.ack_retention_minutes fallback"),
    (re.compile(r"receiptRetentionMinutes:\s*\d+"), "hardcoded pwa.receipt_retention_minutes fallback"),
]


def main() -> int:
    failures: list[str] = []
    for path in sorted(CITIZEN_SRC.rglob("*")):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for pattern, reason in FORBIDDEN:
            if pattern.search(text):
                failures.append(f"{rel}: {reason}")
    if failures:
        for line in failures:
            print(f"::error file={line.split(':')[0]}::{line}")
        return 1
    print("check_pwa_config: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
