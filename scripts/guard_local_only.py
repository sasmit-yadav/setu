#!/usr/bin/env python
"""scripts/guard_local_only.py — refuse destructive commands against a remote DB.

`db-reset` against the Neon demo database on 23 August would be an
unrecoverable, entirely preventable mistake. Six lines of paranoia.
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db", "setu-db", ""}


def main() -> int:
    url = os.environ.get("DATABASE_URL_DIRECT", "")
    if not url:
        print("REFUSING: DATABASE_URL_DIRECT is not set.", file=sys.stderr)
        return 1
    host = (urlparse(url).hostname or "").lower()
    if host not in LOCAL_HOSTS:
        print(
            f"REFUSING: DATABASE_URL_DIRECT points at '{host}', which is not local.\n"
            f"This command destroys data. It only runs against localhost.",
            file=sys.stderr,
        )
        return 1
    print(f"  OK   target is local ({host or 'socket'}) — destructive command permitted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
