from __future__ import annotations

from services.api.snapshot import SNAPSHOT_TABLES


async def test_snapshot_tables_exist(db_conn):
    for table in SNAPSHOT_TABLES:
        exists = await db_conn.fetchval(
            "SELECT to_regclass($1)",
            f"public.{table}",
        )
        assert exists == table, table


async def test_lead_time_view_publishes_coverage(db_conn):
    row = await db_conn.fetchrow("SELECT * FROM v_lead_time_coverage")
    assert row is not None
    assert "coverage_pct" in row
