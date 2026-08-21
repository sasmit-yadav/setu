from __future__ import annotations

import pytest

from scripts.provision_demo_accounts import lookup_unit
from services.api import config_repo


async def test_lookup_unit_finds_configured_officer_scope(db_conn):
    name = await config_repo.get(db_conn, "demo.unit_scope.officer.a@setu.example")
    if not name:
        pytest.skip("demo.unit_scope keys not seeded — run python run.py seed-config")
    unit_id = await lookup_unit(db_conn, name)
    if unit_id is None:
        pytest.skip(f"no admin_unit matching {name!r} — load geometry first")
    row = await db_conn.fetchrow("SELECT id, name FROM admin_unit WHERE id = $1", unit_id)
    assert row is not None
    assert name.lower() in row["name"].lower()


async def test_scope_keys_point_at_seeded_users(db_conn):
    rows = await db_conn.fetch(
        "SELECT key, value FROM app_config WHERE key LIKE 'demo.unit_scope.%'"
    )
    if not rows:
        pytest.skip("demo.unit_scope keys not seeded — run python run.py seed-config")
    for row in rows:
        email = row["key"].removeprefix("demo.unit_scope.")
        exists = await db_conn.fetchval(
            "SELECT id FROM app_user WHERE lower(email) = lower($1)", email
        )
        assert exists is not None, email
