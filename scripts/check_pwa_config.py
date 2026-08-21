#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CITIZEN = ROOT / "web" / "citizen"

FORBIDDEN = [
    (re.compile(r"useState\s*\(\s*280\s*\)"), "hardcoded free_text_max before config load"),
    (re.compile(r"networkTimeoutSeconds:\s*\d+"), "hardcoded pwa.network_timeout_seconds fallback"),
    (re.compile(r"alertCacheMaxAgeSeconds:\s*\d+"), "hardcoded pwa.alert_cache_max_age_seconds fallback"),
    (re.compile(r"ackRetentionMinutes:\s*\d+"), "hardcoded pwa.ack_retention_minutes fallback"),
    (re.compile(r"receiptRetentionMinutes:\s*\d+"), "hardcoded pwa.receipt_retention_minutes fallback"),
    (re.compile(r"HELP_TYPES\s*="), "hardcoded C6 help type list — load response.help_types"),
    (re.compile(r"I am trapped"), "hardcoded C6 label — load response.label.*"),
    (re.compile(r"citizen@setu\.example"), "hardcoded demo email — load demo.citizen_email"),
]

DARK_THEME = re.compile(r"#0f172a", re.IGNORECASE)
SCAN_SUFFIXES = {".ts", ".tsx", ".css", ".html"}


def main() -> int:
    failures: list[str] = []
    for path in sorted(CITIZEN.rglob("*")):
        if path.suffix not in SCAN_SUFFIXES and path.name != "vite.config.ts":
            continue
        if "node_modules" in path.parts or "dist" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix in {".ts", ".tsx"}:
            for pattern, reason in FORBIDDEN:
                if pattern.search(text):
                    failures.append(f"{rel}: {reason}")
        if DARK_THEME.search(text):
            failures.append(f"{rel}: dark theme-color — citizen PWA is light-first")
    if failures:
        for line in failures:
            print(f"::error file={line.split(':')[0]}::{line}")
        return 1
    print("check_pwa_config: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
