#!/usr/bin/env python
"""scripts/set_password.py — set an app_user's password, out of band.

Credentials are NEVER written into data/seeds/*.sql. 06_app_users.sql creates
accounts with password_hash = NULL, which means "cannot log in" — so committing
it creates no usable credential, and a leaked repo grants no access.

    python scripts/set_password.py vythiri.a@setu.local
    python scripts/set_password.py vythiri.a@setu.local --random

--random prints a generated password ONCE and does not store it anywhere but
the bcrypt hash in the database. Use it for the demo accounts; use the
interactive prompt for anything real.

The password is read from a hidden prompt, never from argv — a password passed
as a command-line argument is visible in `ps` and lands in shell history.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.env_loader import load_env_file
from services.api import config_repo
from services.api.auth import hash_password
from services.api.db import connect


async def main_async(email: str, use_random: bool) -> int:
    conn = await connect()
    try:
        row = await conn.fetchrow(
            "SELECT id, role, active FROM app_user WHERE lower(email) = lower($1)", email
        )
        if row is None:
            print(f"No such user: {email}", file=sys.stderr)
            print("Seed accounts first:  python run.py seed", file=sys.stderr)
            return 1

        if use_random:
            password = secrets.token_urlsafe(18)
        else:
            password = getpass.getpass(f"New password for {email}: ")
            confirm = getpass.getpass("Confirm: ")
            if password != confirm:
                print("Passwords do not match.", file=sys.stderr)
                return 1
            if not password:
                print("Empty password refused.", file=sys.stderr)
                return 1

        rounds = await config_repo.get_int(conn, "auth.bcrypt_rounds")
        await conn.execute(
            "UPDATE app_user SET password_hash = $1 WHERE id = $2",
            hash_password(password, rounds=rounds),
            row["id"],
        )
        # Any existing sessions belong to the previous credential.
        await conn.execute(
            "UPDATE refresh_token SET revoked_at = now() "
            "WHERE user_id = $1 AND revoked_at IS NULL",
            row["id"],
        )

        print(f"Password set for {email} (role={row['role']}, bcrypt rounds={rounds}).")
        print("Existing refresh sessions for this account were revoked.")
        if use_random:
            print("\n  Generated password (shown once, not stored anywhere else):")
            print(f"    {password}\n")
        if not row["active"]:
            print("NOTE: this account is inactive and still cannot log in.")
        return 0
    finally:
        await conn.close()


def main() -> int:
    load_env_file(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument(
        "--random",
        action="store_true",
        help="generate a random password and print it once",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args.email, args.random))


if __name__ == "__main__":
    sys.exit(main())
