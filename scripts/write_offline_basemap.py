#!/usr/bin/env python3
from __future__ import annotations

import gzip
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "console" / "public" / "tiles" / "setu-basemap.pmtiles"


def _e7(value: float) -> int:
    return int(value * 10_000_000)


def main() -> int:
    metadata = gzip.compress(
        b'{"name":"setu-offline-placeholder","description":"Background only; unit polygons are GeoJSON overlays.","vector_layers":[]}'
    )
    root = gzip.compress(b"")
    header_size = 127
    root_offset = header_size
    meta_offset = root_offset + len(root)
    header = bytearray(header_size)
    header[0:7] = b"PMTiles"
    header[7] = 3
    struct.pack_into("<Q", header, 8, root_offset)
    struct.pack_into("<Q", header, 16, len(root))
    struct.pack_into("<Q", header, 24, meta_offset)
    struct.pack_into("<Q", header, 32, len(metadata))
    struct.pack_into("<Q", header, 40, meta_offset + len(metadata))
    struct.pack_into("<Q", header, 48, 0)
    struct.pack_into("<Q", header, 56, meta_offset + len(metadata))
    struct.pack_into("<Q", header, 64, 0)
    struct.pack_into("<Q", header, 72, 0)
    struct.pack_into("<Q", header, 80, 0)
    struct.pack_into("<Q", header, 88, 0)
    header[96] = 1
    header[97] = 1
    header[98] = 1
    header[99] = 0
    header[100] = 0
    header[101] = 0
    struct.pack_into("<i", header, 102, _e7(68.0))
    struct.pack_into("<i", header, 106, _e7(6.0))
    struct.pack_into("<i", header, 110, _e7(98.0))
    struct.pack_into("<i", header, 114, _e7(38.0))
    header[118] = 5
    struct.pack_into("<i", header, 119, _e7(78.0))
    struct.pack_into("<i", header, 123, _e7(22.0))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(bytes(header) + root + metadata)
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
