from __future__ import annotations

import pytest

from services.api.db import transaction
from services.governance.approvals import (
    ApprovalError,
    approve,
    ensure_dispatch_allowed,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_officer_cannot_satisfy_quorum(db_conn):
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    incident_id = await db_conn.fetchval(
        """
        INSERT INTO incident (label, incident_type, status, origin_source)
        VALUES ('APR-INC', 'test', 'active', 'manual')
        RETURNING id
        """
    )
    alert_id = await db_conn.fetchval(
        """
        INSERT INTO alert (
            source_id, severity, headline, body, lang, area,
            effective_at, expires_at, raw_checksum, incident_id, lifecycle_status
        )
        SELECT 'manual', 'extreme', 'Headline', 'Body', 'en', geom,
               now(), now() + interval '1 hour', 'checksum', $1, 'draft'
        FROM admin_unit WHERE id = $2
        RETURNING id
        """,
        incident_id,
        unit_id,
    )
    officer_a = await db_conn.fetchval(
        """
        INSERT INTO app_user (email, role) VALUES ('a@test.local', 'officer')
        ON CONFLICT (email) DO UPDATE SET role = EXCLUDED.role
        RETURNING id
        """
    )
    async with transaction(db_conn):
        await approve(db_conn, alert_id, officer_a)
        await approve(db_conn, alert_id, officer_a)
        with pytest.raises(ApprovalError) as exc:
            await ensure_dispatch_allowed(db_conn, alert_id)
    assert exc.value.detail["have"] == 1
    assert exc.value.detail["need"] == 2
