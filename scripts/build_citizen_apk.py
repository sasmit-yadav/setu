#!/usr/bin/env python
"""Build a sideload APK of the hosted citizen PWA.

The laptop has Java 8 and no Android SDK. Docker already runs the rest of
SETU, so the JDK 17 + SDK live in mobile/citizen-apk/Dockerfile. Output:

    mobile/citizen-apk/dist/SETU-citizen.apk

Install on a phone: copy the file, allow 'unknown sources', open it.
Override the wrapped URL with CITIZEN_PWA_URL if you are not using the
Vercel deployment.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
APK_DIR = ROOT / "mobile" / "citizen-apk"
OUT_DIR = APK_DIR / "dist"
APK_NAME = "SETU-citizen.apk"
DEFAULT_URL = "https://setucitizen.vercel.app/"


def main() -> int:
    if shutil.which("docker") is None:
        print("Docker is required to build the APK (no local Android SDK).", file=sys.stderr)
        return 1
    probe = subprocess.run(
        ["docker", "info"], capture_output=True, timeout=20
    )
    if probe.returncode != 0:
        print("Docker daemon is not running. Start Docker Desktop and retry.", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pwa_url = os.environ.get("CITIZEN_PWA_URL", DEFAULT_URL).strip() or DEFAULT_URL
    print(f"  wrapping {pwa_url}")
    print("  first build downloads the Android SDK into a Docker layer (~few minutes)")

    cmd = [
        "docker",
        "build",
        "--target",
        "export",
        "--build-arg",
        f"CITIZEN_PWA_URL={pwa_url}",
        "-o",
        str(OUT_DIR),
        str(APK_DIR),
    ]
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.call(cmd)
    if result != 0:
        return result

    apk = OUT_DIR / APK_NAME
    if not apk.is_file():
        print(f"FAILED: expected {apk}", file=sys.stderr)
        return 1

    size = apk.stat().st_size
    if size >= 1024 * 1024:
        size_s = f"{size / (1024 * 1024):.1f} MB"
    else:
        size_s = f"{size / 1024:.0f} KB"
    print()
    print(f"  APK  {apk}")
    print(f"  size {size_s}  (debug-signed, sideload only)")
    print()
    print("  On the phone: Settings -> allow install from this source -> open the APK.")
    print("  This is a fullscreen WebView of the live PWA, not a Play Store listing.")
    print("  Enable-alerts / FCM may fail in WebView; Chrome 'Add to Home Screen'")
    print("  is still the path that proves push delivery.")
    if shutil.which("adb"):
        print()
        print(f"  adb install -r \"{apk}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
