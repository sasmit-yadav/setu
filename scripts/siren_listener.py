#!/usr/bin/env python3
"""Stand-in for a panchayat siren controller.

`WebhookSirenAdapter` is a real HTTP client: it POSTs the alert to whatever
`channel.config->>'webhook_url'` names, and a non-2xx answer raises
ChannelUnavailable. The seed ships `{}` for the siren row, so the URL fell
back to the API root, every POST 404'd, and every siren delivery ended up on
the simulated path. That is a missing config value, not a missing feature.

This server is the other end of that webhook. Point the siren channel at it
and the delivery becomes a real one — `simulated = false`, a genuine
`provider_accepted` row, and a noise in the room. The assurance ladder still
strikes three rungs, because the adapter declares supports_device_delivered
/ supports_opened / supports_acknowledgement False: a siren cannot tell you
anyone heard it, and nothing here pretends otherwise.

The worker runs on this laptop (`run.py worker-cloud`), so 127.0.0.1 is
reachable without a tunnel.

    python scripts/siren_listener.py                 # :9099
    python scripts/siren_listener.py --port 9500
    python scripts/siren_listener.py --silent        # log only, no audio

Then, once:

    UPDATE channel
       SET config = '{"webhook_url":"http://127.0.0.1:9099/siren"}'::jsonb
     WHERE code = 'siren';
"""

from __future__ import annotations

import argparse
import array
import datetime
import json
import math
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# A rising-falling wail, synthesised once into a WAV and played through the
# default audio device. The first version used winsound.Beep, which drives the
# motherboard timer rather than the sound card - on most modern laptops that is
# inaudible, so the siren "worked" in the logs and made no noise in the room.
SWEEP_LOW_HZ = 500.0
SWEEP_HIGH_HZ = 1400.0
WAIL_SECONDS = 1.2      # one rise-and-fall
WAIL_CYCLES = 3
SAMPLE_RATE = 44100
AMPLITUDE = 0.55        # loud enough to carry, short of clipping
MAX_BODY_BYTES = 64 * 1024

_WAV_PATH: pathlib.Path | None = None


def _siren_wav() -> pathlib.Path | None:
    """Synthesise the wail once and cache it next to the OS temp dir."""
    global _WAV_PATH
    if _WAV_PATH is not None:
        return _WAV_PATH if _WAV_PATH.exists() else None
    target = pathlib.Path(tempfile.gettempdir()) / "setu-siren.wav"
    try:
        total = int(SAMPLE_RATE * WAIL_SECONDS * WAIL_CYCLES)
        frames = array.array("h")
        phase = 0.0
        for n in range(total):
            # Position within one rise-and-fall, 0..1..0
            cycle_pos = (n % int(SAMPLE_RATE * WAIL_SECONDS)) / (SAMPLE_RATE * WAIL_SECONDS)
            sweep = 1.0 - abs(2.0 * cycle_pos - 1.0)
            freq = SWEEP_LOW_HZ + (SWEEP_HIGH_HZ - SWEEP_LOW_HZ) * sweep
            # Integrate frequency into phase, or a changing freq clicks.
            phase += 2.0 * math.pi * freq / SAMPLE_RATE
            frames.append(int(AMPLITUDE * 32767 * math.sin(phase)))
        with wave.open(str(target), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(SAMPLE_RATE)
            out.writeframes(frames.tobytes())
    except OSError:
        return None
    _WAV_PATH = target
    return target


def _sound_siren() -> None:
    """Make a noise on the default output. Falls back rather than failing."""
    try:
        import winsound
    except ImportError:
        # Not Windows. Let the desktop try; the log line is still the record.
        for player in (("aplay",), ("afplay",), ("paplay",)):
            wav = _siren_wav()
            if wav is None:
                return
            try:
                subprocess.run([*player, str(wav)], check=False, timeout=10)
                return
            except (OSError, subprocess.SubprocessError):
                continue
        return
    wav = _siren_wav()
    if wav is not None:
        try:
            winsound.PlaySound(str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        except RuntimeError:
            pass
    # Last resorts: a system sound uses the sound card; Beep may not.
    try:
        winsound.MessageBeep(winsound.MB_ICONHAND)
    except RuntimeError:
        pass


def _force_utf8_stdout() -> None:
    """A Malayalam headline must not kill the siren.

    Windows consoles default to cp1252, and print() of an alert headline in
    Malayalam raises UnicodeEncodeError - which took this listener down mid-run
    the first time a real translated warning reached it. The worker documents
    PYTHONIOENCODING=utf-8 for the same reason; relying on the operator
    remembering an env var is how the demo loses its siren.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).astimezone().strftime("%H:%M:%S")


class SirenHandler(BaseHTTPRequestHandler):
    silent = False

    # do_POST / do_GET are BaseHTTPRequestHandler's dispatch names, not ours.
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            self.send_error(413, "payload too large")
            return
        raw = self.rfile.read(length) if length else b""
        # Decode before parsing, replacing anything malformed. json.loads() on
        # bytes raises UnicodeDecodeError rather than JSONDecodeError, so a body
        # with one bad byte escaped the handler entirely. A siren controller must
        # sound on a request it cannot fully read - refusing to make a noise
        # because the headline had a stray byte is the wrong failure.
        text = raw.decode("utf-8", "replace") if raw else "{}"
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            payload = {"_unparsed": text[:200]}
        if not isinstance(payload, dict):
            payload = {"_unparsed": text[:200]}

        alert = payload.get("alert_id", "?")
        delivery = payload.get("delivery_id", "?")
        headline = payload.get("headline", "(no headline)")
        print(f"[{_now()}] SIREN  alert={alert} delivery={delivery}  {headline}", flush=True)

        if not self.silent:
            threading.Thread(target=_sound_siren, daemon=True).start()

        body = json.dumps({"sounded": True, "delivery_id": delivery}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        body = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        """Silence the default per-request access log; our own line is clearer."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9099)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--silent", action="store_true", help="log only, no audio")
    parser.add_argument(
        "--test",
        action="store_true",
        help="play the siren once and exit - check the speakers before the demo",
    )
    args = parser.parse_args()

    if args.test:
        _force_utf8_stdout()
        wav = _siren_wav()
        if wav is None:
            print("could not synthesise the siren wav", file=sys.stderr)
            return 1
        print(f"playing {wav} ({wav.stat().st_size // 1024} KB) - you should hear a wail")
        _sound_siren()
        # PlaySound is async; hold the process open long enough to finish.
        time.sleep(WAIL_SECONDS * WAIL_CYCLES + 1)
        print("if you heard nothing: check the output device and system volume")
        return 0

    _force_utf8_stdout()
    SirenHandler.silent = args.silent
    server = ThreadingHTTPServer((args.host, args.port), SirenHandler)
    audio = "log only" if args.silent else "audible"
    print(f"siren listener on http://{args.host}:{args.port}/siren  ({audio})", flush=True)
    print("keep this terminal visible during the demo. ctrl-c to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nsiren listener stopped.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
