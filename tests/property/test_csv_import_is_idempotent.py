from __future__ import annotations

import os
import uuid

import pytest

from services.enrollment.csv_import import import_csv
from services.enrollment.phone_hash import phone_hash


@pytest.mark.integration
@pytest.mark.asyncio
async def test_csv_import_is_idempotent(db_conn):
    if not os.environ.get("PHONE_HASH_PEPPER"):
        pytest.skip("PHONE_HASH_PEPPER not set")
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    phone = f"+9199{uuid.uuid4().int % 10_000_000_000:010d}"
    csv_body = f"phone,unit_id,preferred_lang\n{phone},{unit_id},en\n".encode()
    dry = await import_csv(db_conn, csv_body, dry_run=True, actor="property")
    live = await import_csv(
        db_conn,
        csv_body,
        dry_run=False,
        actor="property",
        preview_token=dry.preview_token,
    )
    assert live.inserted == 1
    again = await import_csv(
        db_conn,
        csv_body,
        dry_run=False,
        actor="property",
        preview_token=dry.preview_token,
    )
    assert again.inserted == 0
    assert again.skipped == 1
    digest = phone_hash(phone)
    count = await db_conn.fetchval("SELECT COUNT(*) FROM recipient WHERE phone_hash = $1", digest)
    assert count == 1
