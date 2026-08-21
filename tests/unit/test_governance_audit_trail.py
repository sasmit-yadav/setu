"""Approvals and validation failures must reach the immutable ledger.

Part 16's Day 6 DoD requires the incident timeline to contain, by name,
`alert.validation_failed` and `alert.approved`. Neither was ever written:
`services/governance/approvals.py` had no audit call at all, and the
`/validate` endpoint persisted per-rule rows to `alert_validation_result`
without appending a ledger entry. Both are the marquee governance features
(F1 and F3, each below the cut line), so an approval that leaves no audit
trace defeats the point of the ledger existing — a full test suite passed
over it because no test asserted on the ledger's *contents* after approving.

These tests assert on `audit_event` directly rather than on the timeline
endpoint, so they fail at the writer rather than at the reader.
"""

from __future__ import annotations

import uuid

import pytest

from services.governance.approvals import approve, record_auto_approval


async def _incident(conn, label: str) -> int:
    return await conn.fetchval(
        """
        INSERT INTO incident (label, incident_type, status, origin_source)
        VALUES ($1, 'test', 'active', 'manual')
        RETURNING id
        """,
        label,
    )


async def _alert(conn, incident_id: int, *, source_id: str = "manual") -> int:
    unit_id = await conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    return await conn.fetchval(
        """
        INSERT INTO alert (
            source_id, severity, headline, body, lang, area,
            effective_at, expires_at, raw_checksum, incident_id, lifecycle_status
        )
        SELECT $1, 'severe', 'Audit trail', 'Body', 'en', geom,
               now(), now() + interval '2 hours', $2, $3, 'draft'
        FROM admin_unit WHERE id = $4
        RETURNING id
        """,
        source_id,
        f"checksum-audit-{uuid.uuid4().hex[:10]}",
        incident_id,
        unit_id,
    )


async def _audit_types(conn, alert_id: int) -> list[str]:
    rows = await conn.fetch(
        "SELECT event_type FROM audit_event WHERE alert_id = $1 ORDER BY id",
        alert_id,
    )
    return [r["event_type"] for r in rows]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_human_approval_appends_alert_approved(db_conn):
    incident_id = await _incident(db_conn, f"AUD-{uuid.uuid4().hex[:6]}")
    alert_id = await _alert(db_conn, incident_id)
    officer = await db_conn.fetchval("SELECT id FROM app_user LIMIT 1")

    await approve(db_conn, alert_id, officer, reason="looks right", actor="officer.a@setu.example")

    assert "alert.approved" in await _audit_types(db_conn, alert_id)
    row = await db_conn.fetchrow(
        """
        SELECT actor, payload FROM audit_event
        WHERE alert_id = $1 AND event_type = 'alert.approved'
        """,
        alert_id,
    )
    assert row["actor"] == "officer.a@setu.example"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_same_officer_approving_twice_appends_only_one_audit_row(db_conn):
    """F3's guarantee is that one human cannot self-quorum. The ledger must
    agree with `alert_approval`: two audit rows for one approval would imply a
    second approver who does not exist."""
    incident_id = await _incident(db_conn, f"AUD-{uuid.uuid4().hex[:6]}")
    alert_id = await _alert(db_conn, incident_id)
    officer = await db_conn.fetchval("SELECT id FROM app_user LIMIT 1")

    await approve(db_conn, alert_id, officer, reason="first", actor="officer.a@setu.example")
    await approve(db_conn, alert_id, officer, reason="again", actor="officer.a@setu.example")

    approved_events = await db_conn.fetchval(
        """
        SELECT COUNT(*) FROM audit_event
        WHERE alert_id = $1 AND event_type = 'alert.approved'
        """,
        alert_id,
    )
    approval_rows = await db_conn.fetchval(
        "SELECT COUNT(*) FROM alert_approval WHERE alert_id = $1", alert_id
    )
    assert approved_events == 1
    assert approval_rows == 1
    assert approved_events == approval_rows


@pytest.mark.integration
@pytest.mark.asyncio
async def test_two_distinct_officers_append_two_audit_rows(db_conn):
    incident_id = await _incident(db_conn, f"AUD-{uuid.uuid4().hex[:6]}")
    alert_id = await _alert(db_conn, incident_id)
    officers = [
        r["id"]
        for r in await db_conn.fetch("SELECT id FROM app_user ORDER BY id LIMIT 2")
    ]
    if len(officers) < 2:
        pytest.skip("need two app_user rows")

    await approve(db_conn, alert_id, officers[0], actor="officer.a@setu.example")
    have = await approve(db_conn, alert_id, officers[1], actor="officer.b@setu.example")

    assert have == 2
    actors = [
        r["actor"]
        for r in await db_conn.fetch(
            """
            SELECT actor FROM audit_event
            WHERE alert_id = $1 AND event_type = 'alert.approved' ORDER BY id
            """,
            alert_id,
        )
    ]
    assert actors == ["officer.a@setu.example", "officer.b@setu.example"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_authoritative_auto_approval_is_audited(db_conn):
    """Rule 12's machine path must be visible too. "The seismograph is the
    second pair of eyes" is only defensible if the ledger records it."""
    incident_id = await _incident(db_conn, f"AUD-{uuid.uuid4().hex[:6]}")
    alert_id = await _alert(db_conn, incident_id, source_id="usgs")

    await record_auto_approval(db_conn, alert_id)

    row = await db_conn.fetchrow(
        """
        SELECT actor, payload FROM audit_event
        WHERE alert_id = $1 AND event_type = 'alert.approved'
        """,
        alert_id,
    )
    assert row is not None, "auto-approval left no ledger entry"
    assert "authoritative_source" in str(row["payload"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auto_approval_is_idempotent_in_the_ledger(db_conn):
    incident_id = await _incident(db_conn, f"AUD-{uuid.uuid4().hex[:6]}")
    alert_id = await _alert(db_conn, incident_id, source_id="usgs")

    await record_auto_approval(db_conn, alert_id)
    await record_auto_approval(db_conn, alert_id)

    n = await db_conn.fetchval(
        """
        SELECT COUNT(*) FROM audit_event
        WHERE alert_id = $1 AND event_type = 'alert.approved'
        """,
        alert_id,
    )
    assert n == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_validate_endpoint_audits_a_blocking_failure(db_conn):
    """The composer's own validate call (Day-9 run, step 3) is where a blocked
    dispatch becomes visible to the officer, so it is the call that has to land
    in the timeline. `alert_validation_result` is per-rule state, not a ledger
    entry — before this, a blocked alert produced no audit_event at all."""
    from httpx import ASGITransport, AsyncClient

    from services.api.auth import Principal, issue_access_token
    from services.api.main import app

    incident_id = await _incident(db_conn, f"AUD-{uuid.uuid4().hex[:6]}")
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    # expires_at NULL trips expiry_set, which is a blocking failure.
    alert_id = await db_conn.fetchval(
        """
        INSERT INTO alert (
            source_id, severity, headline, body, lang, area,
            effective_at, expires_at, raw_checksum, incident_id, lifecycle_status
        )
        SELECT 'manual', 'severe', 'No expiry', 'Body', 'en', geom,
               now(), NULL, $1, $2, 'draft'
        FROM admin_unit WHERE id = $3
        RETURNING id
        """,
        f"checksum-vf-{uuid.uuid4().hex[:10]}",
        incident_id,
        unit_id,
    )

    principal = Principal(
        user_id=await db_conn.fetchval("SELECT id FROM app_user LIMIT 1"),
        email="officer.audit@setu.example",
        role="officer",
        unit_scope_id=None,
    )
    token, _ = await issue_access_token(db_conn, principal)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            f"/api/v1/alerts/{alert_id}/validate",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200, r.text
    assert r.json()["blocked"] is True

    row = await db_conn.fetchrow(
        """
        SELECT actor, payload FROM audit_event
        WHERE alert_id = $1 AND event_type = 'alert.validation_failed'
        """,
        alert_id,
    )
    assert row is not None, "a blocked validation left no ledger entry"
    assert "expiry_set" in str(row["payload"])
    assert row["actor"] == "officer.audit@setu.example"
