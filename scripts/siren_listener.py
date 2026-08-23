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
import datetime
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# A rising-falling two-tone sweep reads as "siren" without shipping a WAV.
SWEEP_LOW_HZ = 600
SWEEP_HIGH_HZ = 1200
SWEEP_STEP_HZ = 100
SWEEP_STEP_MS = 40
SWEEP_CYCLES = 3
MAX_BODY_BYTES = 64 * 1024


def _beep_sweep() -> None:
    """Windows-only audio. Anywhere else the log line is the whole output."""
    try:
        import winsound
    except ImportError:
        return
    for _ in range(SWEEP_CYCLES):
        for hz in range(SWEEP_LOW_HZ, SWEEP_HIGH_HZ, SWEEP_STEP_HZ):
            winsound.Beep(hz, SWEEP_STEP_MS)
        for hz in range(SWEEP_HIGH_HZ, SWEEP_LOW_HZ, -SWEEP_STEP_HZ):
            winsound.Beep(hz, SWEEP_STEP_MS)


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
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            payload = {"_unparsed": raw[:200].decode("utf-8", "replace")}

        alert = payload.get("alert_id", "?")
        delivery = payload.get("delivery_id", "?")
        headline = payload.get("headline", "(no headline)")
        print(f"[{_now()}] SIREN  alert={alert} delivery={delivery}  {headline}", flush=True)

        if not self.silent:
            threading.Thread(target=_beep_sweep, daemon=True).start()

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
    args = parser.parse_args()

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
