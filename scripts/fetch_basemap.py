#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "console" / "public" / "tiles" / "setu-basemap.pmtiles"
CACHE = ROOT / ".cache" / "pmtiles"
CLI_VERSION = "1.30.1"
BBOX = "68,6,98,38"
MAXZOOM = "6"


def _asset() -> tuple[str, str]:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        name = f"go-pmtiles_{CLI_VERSION}_Windows_x86_64.zip"
        return name, "pmtiles.exe"
    if system == "Darwin" and machine in {"arm64", "aarch64"}:
        name = f"go-pmtiles-{CLI_VERSION}_Darwin_arm64.zip"
        return name, "pmtiles"
    if system == "Darwin":
        name = f"go-pmtiles-{CLI_VERSION}_Darwin_x86_64.zip"
        return name, "pmtiles"
    if machine in {"arm64", "aarch64"}:
        name = f"go-pmtiles_{CLI_VERSION}_Linux_arm64.tar.gz"
        return name, "pmtiles"
    name = f"go-pmtiles_{CLI_VERSION}_Linux_x86_64.tar.gz"
    return name, "pmtiles"


def _ensure_cli() -> Path | None:
    found = shutil.which("pmtiles")
    if found:
        return Path(found)
    CACHE.mkdir(parents=True, exist_ok=True)
    asset, binary_name = _asset()
    dest = CACHE / binary_name
    if dest.exists():
        return dest
    url = f"https://github.com/protomaps/go-pmtiles/releases/download/v{CLI_VERSION}/{asset}"
    archive = CACHE / asset
    print(f"fetch_basemap: downloading {url}")
    try:
        urllib.request.urlretrieve(url, archive)
    except OSError as exc:
        print(f"fetch_basemap: CLI download failed ({exc})")
        return None
    if asset.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                if Path(info.filename).name in {"pmtiles", "pmtiles.exe"}:
                    info.filename = binary_name
                    zf.extract(info, CACHE)
                    break
    else:
        with tarfile.open(archive, "r:gz") as tf:
            member = next(
                (m for m in tf.getmembers() if Path(m.name).name == "pmtiles"),
                None,
            )
            if member is None:
                return None
            member.name = binary_name
            tf.extract(member, CACHE)
    if not dest.exists():
        return None
    dest.chmod(dest.stat().st_mode | 0o111)
    return dest


def _extract(cli: Path, source: str) -> bool:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(cli),
        "extract",
        source,
        str(OUT),
        f"--bbox={BBOX}",
        f"--maxzoom={MAXZOOM}",
    ]
    print("  $", " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT) == 0 and OUT.exists() and OUT.stat().st_size > 2048


def _placeholder() -> None:
    writer = ROOT / "scripts" / "write_offline_basemap.py"
    subprocess.check_call([sys.executable, str(writer)], cwd=ROOT)
    print("fetch_basemap: wrote placeholder (no Protomaps extract)")


def main() -> int:
    cli = _ensure_cli()
    if cli is None:
        _placeholder()
        return 0
    today = dt.date.today()
    for offset in range(0, 8):
        stamp = (today - dt.timedelta(days=offset)).strftime("%Y%m%d")
        url = f"https://build.protomaps.com/{stamp}.pmtiles"
        print(f"fetch_basemap: trying {url}")
        if _extract(cli, url):
            print(f"fetch_basemap: {OUT} ({OUT.stat().st_size} bytes)")
            return 0
    _placeholder()
    return 0


if __name__ == "__main__":
    sys.exit(main())
