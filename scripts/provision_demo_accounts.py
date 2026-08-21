#!/usr/bin/env python
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.env_loader import direct_dsn, load_env_file
from services.api import config_repo
from services.api.auth import hash_password
from services.api.db import connect

SCOPE_PREFIX = "demo.unit_scope."
USERS_SEED = ROOT / "data" / "seeds" / "06_app_users.sql"


def ensure_seed_users() -> None:
    if not USERS_SEED.exists():
        raise SystemExit(f"missing {USERS_SEED}")
    import psycopg

    sql = USERS_SEED.read_text(encoding="utf-8")
    with psycopg.connect(direct_dsn()) as conn:
        conn.execute(sql)
        conn.commit()


async def lookup_unit(conn, name: str) -> int | None:
    needle = name.strip()
    if not needle:
        return None
    exact = await conn.fetchval(
        """
        SELECT id FROM admin_unit
        WHERE name ILIKE $1
        ORDER BY level ASC, id
        LIMIT 1
        """,
        needle,
    )
    if exact is not None:
        return int(exact)
    fuzzy = await conn.fetchval(
        """
        SELECT id FROM admin_unit
        WHERE name ILIKE $1
        ORDER BY level ASC, id
        LIMIT 1
        """,
        f"%{needle}%",
    )
    return int(fuzzy) if fuzzy is not None else None


async def apply_scopes(conn) -> list[str]:
    rows = await conn.fetch(
        "SELECT key, value FROM app_config WHERE key LIKE $1 ORDER BY key",
        f"{SCOPE_PREFIX}%",
    )
    if not rows:
        raise SystemExit(
            "No demo.unit_scope.* keys in app_config — run: python run.py seed-config"
        )
    failures: list[str] = []
    for row in rows:
        email = row["key"].removeprefix(SCOPE_PREFIX).strip()
        name = (row["value"] or "").strip()
        if not email:
            failures.append(row["key"])
            print(f"  FAIL {row['key']}: empty email suffix", file=sys.stderr)
            continue
        user_id = await conn.fetchval(
            "SELECT id FROM app_user WHERE lower(email) = lower($1)", email
        )
        if user_id is None:
            failures.append(email)
            print(f"  FAIL {email}: no app_user row", file=sys.stderr)
            continue
        unit_id = await lookup_unit(conn, name)
        if unit_id is None:
            failures.append(email)
            print(f"  FAIL {email}: no admin_unit matching {name!r}", file=sys.stderr)
            continue
        await conn.execute(
            "UPDATE app_user SET unit_scope_id = $1 WHERE id = $2",
            unit_id,
            user_id,
        )
        print(f"  OK {email} -> unit_id={unit_id} ({name})")
    return failures


async def apply_passwords(conn) -> None:
    password = os.environ.get("SETU_DEMO_PASSWORD", "").strip()
    if not password:
        print("SETU_DEMO_PASSWORD empty - scopes assigned, accounts still cannot log in.")
        return
    emails = await config_repo.get_csv(conn, "demo.password_emails")
    if not emails:
        raise SystemExit("demo.password_emails is empty")
    rounds = await config_repo.get_int(conn, "auth.bcrypt_rounds")
    hashed = hash_password(password, rounds=rounds)
    updated = 0
    for email in emails:
        user_id = await conn.fetchval(
            "SELECT id FROM app_user WHERE lower(email) = lower($1)", email
        )
        if user_id is None:
            print(f"  FAIL password: no app_user row for {email}", file=sys.stderr)
            continue
        await conn.execute(
            "UPDATE app_user SET password_hash = $1 WHERE id = $2",
            hashed,
            user_id,
        )
        await conn.execute(
            "UPDATE refresh_token SET revoked_at = now() "
            "WHERE user_id = $1 AND revoked_at IS NULL",
            user_id,
        )
        updated += 1
    print(f"Password hash updated for {updated} demo accounts (not printed).")


async def main_async() -> int:
    conn = await connect()
    try:
        failures = await apply_scopes(conn)
        await apply_passwords(conn)
    finally:
        await conn.close()
    if failures:
        print(f"FAILED: {len(failures)} scope assignment(s)", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    env_path = os.environ.get("SETU_ENV_FILE")
    if env_path:
        load_env_file(Path(env_path), override=True)
    else:
        load_env_file(ROOT / ".env")
    ensure_seed_users()
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
