#!/usr/bin/env python
"""scripts/wait_for_db.py — block until Postgres and Redis are actually ready.

`docker compose up -d` returns the moment the containers START, not the moment
Postgres can accept a connection. Running alembic immediately after it fails
with a connection error that looks like a config problem and is not.
"""

from __future__ import annotations

import socket
import sys
import time

TIMEOUT_S = 60
# 5433, not 5432 — see the note in infra/docker-compose.yml and scripts/doctor.py:
# this machine has a native postgres.exe already on 5432, which would make this
# check pass while the actual setu-db container was never reached.
TARGETS = [("postgres", "localhost", 5433), ("redis", "localhost", 6379)]


def wait(name: str, host: str, port: int, deadline: float) -> bool:
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"  OK   {name} on {host}:{port}")
                return True
        except OSError:
            time.sleep(1)
    print(f"  FAIL {name} on {host}:{port} did not accept a connection in {TIMEOUT_S}s")
    return False


def main() -> int:
    print(f"Waiting for local services (timeout {TIMEOUT_S}s)...")
    deadline = time.time() + TIMEOUT_S
    ok = all(wait(n, h, p, deadline) for n, h, p in TARGETS)
    if not ok:
        print(
            "\nIs Docker Desktop running?  Then:  docker compose -f infra/docker-compose.yml up -d",
            file=sys.stderr,
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
