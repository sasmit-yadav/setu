from __future__ import annotations

import os
import uuid

import pytest

from services.enrollment.csv_import import import_csv
from services.enrollment.phone_hash import phone_hash
from services.governance.composer import create_draft_alert


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_draft_alert_from_units(db_conn):
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    result = await create_draft_alert(
        db_conn,
        severity="moderate",
        headline="Road flooding",
        body="Avoid low-lying areas",
        lang="en",
        unit_ids=[unit_id],
    )
    assert result["lifecycle_status"] == "draft"
    assert result["target_count"] >= 0
    row = await db_conn.fetchrow("SELECT incident_id, lifecycle_status FROM alert WHERE id = $1", result["alert_id"])
    assert row["incident_id"] == result["incident_id"]
    assert row["lifecycle_status"] == "draft"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_csv_import_dry_run_then_insert(db_conn):
    if not os.environ.get("PHONE_HASH_PEPPER"):
        pytest.skip("PHONE_HASH_PEPPER not set")
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    phone = f"+9199{uuid.uuid4().int % 10_000_000_000:010d}"
    csv_body = f"phone,unit_id,preferred_lang\n{phone},{unit_id},en\n".encode()
    dry = await import_csv(db_conn, csv_body, dry_run=True, actor="test")
    assert dry.inserted == 1
    assert dry.dry_run is True
    live = await import_csv(
        db_conn,
        csv_body,
        dry_run=False,
        actor="test",
        preview_token=dry.preview_token,
    )
    assert live.inserted == 1
    assert live.dry_run is False
    digest = phone_hash(phone)
    count = await db_conn.fetchval("SELECT COUNT(*) FROM recipient WHERE phone_hash = $1", digest)
    assert count == 1
    again = await import_csv(
        db_conn,
        csv_body,
        dry_run=False,
        actor="test",
        preview_token=dry.preview_token,
    )
    assert again.skipped == 1
    assert again.inserted == 0
