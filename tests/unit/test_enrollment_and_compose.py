from __future__ import annotations

import os
import uuid

import pytest

from services.enrollment.csv_import import import_csv
from services.enrollment.phone_hash import phone_hash
from services.governance.composer import create_draft_alert
from services.ingestion.incident_linker import detach_if_incident_already_live


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
async def test_detach_if_incident_already_live_splits_fresh_compose(db_conn):
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    first = await create_draft_alert(
        db_conn,
        severity="extreme",
        headline="First live",
        body="Stay inside",
        lang="en",
        unit_ids=[unit_id],
    )
    await db_conn.execute(
        "UPDATE alert SET lifecycle_status = 'active' WHERE id = $1",
        first["alert_id"],
    )
    second = await create_draft_alert(
        db_conn,
        severity="extreme",
        headline="Second draft",
        body="Move higher",
        lang="en",
        unit_ids=[unit_id],
    )
    await db_conn.execute(
        "UPDATE alert SET incident_id = $1 WHERE id = $2",
        first["incident_id"],
        second["alert_id"],
    )
    new_incident = await detach_if_incident_already_live(
        db_conn, second["alert_id"], actor="tester"
    )
    assert new_incident is not None
    assert new_incident != first["incident_id"]
    row = await db_conn.fetchrow(
        "SELECT incident_id FROM alert WHERE id = $1", second["alert_id"]
    )
    assert int(row["incident_id"]) == new_incident
    still = await detach_if_incident_already_live(
        db_conn, second["alert_id"], actor="tester"
    )
    assert still is None


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
