#!/usr/bin/env python
"""Generate the citizen PWA's icon set.

`vite.config.ts` and `src/sw.ts` both referenced `/icon-192.png` and the file
did not exist — there was no `public/` directory at all. Two consequences, both
demo-visible: Chrome will not offer "add to home screen" without a valid
manifest icon, and `showNotification({icon: ...})` silently renders unbranded,
which is a weak moment when the whole beat is a real push landing on a phone
held up to judges.

Generated rather than committed-as-a-binary-blob so the colour stays tied to the
palette instead of drifting: the fill is `--state-pending` (#1d70b8) from
`src/styles.css`, the same token the brand mark uses. Regenerate with:

    python scripts/gen_pwa_icons.py

The glyph is an arch bridge, which is what "setu" means. It is drawn inside the
central 60% of the canvas so the same asset is safe as a `maskable` icon —
Android crops maskable icons to a circle and anything in the outer band is lost.

Pure stdlib on purpose: PIL is not in requirements.txt, and adding a build-time
image dependency to ship two flat PNGs would be a poor trade.
"""

from __future__ import annotations

import pathlib
import struct
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "web" / "citizen" / "public"

# --state-pending from web/citizen/src/styles.css. Keep these in step.
BG = (0x1D, 0x70, 0xB8)
FG = (0xFF, 0xFF, 0xFF)

SIZES = (192, 512)


def _png(width: int, height: int, rgb_rows: list[bytearray]) -> bytes:
    """Minimal RGB PNG. Filter type 0 (None) on every scanline."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit, truecolour
    raw = b"".join(b"\x00" + bytes(row) for row in rgb_rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _render(size: int) -> list[bytearray]:
    """An arch bridge: a deck, a semicircular arch under it, two piers."""
    cx = size / 2.0
    # Everything sits inside the central 60% so the icon survives a maskable
    # circular crop. `inset` is where the drawable area starts.
    inset = size * 0.20
    span = size - 2 * inset

    stroke = max(2.0, span * 0.11)          # line weight, scales with the icon
    deck_y = inset + span * 0.46            # top of the deck
    arch_r = span * 0.40                    # arch radius, centred on the deck
    pier_top = deck_y + stroke
    pier_bottom = inset + span * 0.92
    pier_inset = inset + span * 0.06

    rows: list[bytearray] = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            px, py = x + 0.5, y + 0.5
            on = False

            # Deck: a horizontal bar across the full drawable span.
            if deck_y <= py <= deck_y + stroke and inset <= px <= size - inset:
                on = True

            # Arch: the lower half of an annulus centred on the deck line.
            if not on and py >= deck_y:
                d = ((px - cx) ** 2 + (py - deck_y) ** 2) ** 0.5
                if arch_r - stroke <= d <= arch_r:
                    on = True

            # Piers: two verticals carrying the deck down to the baseline.
            in_pier_x = (
                pier_inset <= px <= pier_inset + stroke
                or size - pier_inset - stroke <= px <= size - pier_inset
            )
            if not on and pier_top <= py <= pier_bottom and in_pier_x:
                on = True

            row += bytes(FG if on else BG)
        rows.append(row)
    return rows


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        path = OUT_DIR / f"icon-{size}.png"
        path.write_bytes(_png(size, size, _render(size)))
        print(f"wrote {path.relative_to(ROOT).as_posix()} ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
