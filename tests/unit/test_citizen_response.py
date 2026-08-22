from __future__ import annotations

import uuid

import pytest

from services.api import config_repo
from services.governance.versioning import create_new_version
from services.response.citizen_response import ResponseError, record_from_dtmf, submit_response


@pytest.mark.integration
@pytest.mark.asyncio
async def test_submit_trapped_creates_assistance_case(db_conn, delivery_row):
    key = f"test-{uuid.uuid4()}"
    result = await submit_response(
        db_conn,
        delivery_id=delivery_row["id"],
        response_type="trapped",
        idempotency_key=key,
    )
    assert result["duplicate"] is False
    assert result["assistance_case_id"] is not None
    dup = await submit_response(
        db_conn,
        delivery_id=delivery_row["id"],
        response_type="trapped",
        idempotency_key=key,
    )
    assert dup["duplicate"] is True
    assert dup["citizen_response_id"] == result["citizen_response_id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_submit_safe_skips_assistance_case(db_conn, delivery_row):
    result = await submit_response(
        db_conn,
        delivery_id=delivery_row["id"],
        response_type="safe",
        idempotency_key=f"safe-{uuid.uuid4()}",
    )
    assert result["assistance_case_id"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_location_requires_consent(db_conn, delivery_row):
    with pytest.raises(ResponseError) as exc:
        await submit_response(
            db_conn,
            delivery_id=delivery_row["id"],
            response_type="trapped",
            idempotency_key=f"loc-{uuid.uuid4()}",
            location=(76.0, 11.8),
            location_consent=False,
        )
    assert exc.value.code == "location_consent_required"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_new_version_increments(db_conn):
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    incident_id = await db_conn.fetchval(
        """
        INSERT INTO incident (label, incident_type, status, origin_source)
        VALUES ('VER-INC', 'test', 'active', 'manual')
        RETURNING id
        """
    )
    alert_id = await db_conn.fetchval(
        """
        INSERT INTO alert (
            source_id, severity, headline, body, lang, area,
            effective_at, expires_at, raw_checksum, incident_id,
            version_number, lifecycle_status
        )
        SELECT 'manual', 'moderate', 'v1', 'Body', 'en', geom,
               now(), now() + interval '2 hours', 'v1-checksum', $1,
               1, 'active'
        FROM admin_unit WHERE id = $2
        RETURNING id
        """,
        incident_id,
        unit_id,
    )
    new_id = await create_new_version(
        db_conn,
        alert_id,
        change_reason="Forecast worsened",
        severity="extreme",
    )
    version_number = await db_conn.fetchval(
        "SELECT version_number FROM alert WHERE id = $1",
        new_id,
    )
    supersedes = await db_conn.fetchval(
        "SELECT supersedes_alert_id FROM alert WHERE id = $1",
        new_id,
    )
    assert version_number == 2
    assert supersedes == alert_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dtmf_need_help_writes_response(db_conn, delivery_row):
    digit = await config_repo.get_str(db_conn, "ivr.dtmf.need_help")
    result = await record_from_dtmf(db_conn, delivery_row["id"], digit)
    assert result is not None
    assert result["response_type"] == "other"
    assert result["assistance_case_id"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dtmf_safe_writes_response(db_conn, delivery_row):
    digit = await config_repo.get_str(db_conn, "ivr.dtmf.safe")
    result = await record_from_dtmf(db_conn, delivery_row["id"], digit)
    assert result is not None
    assert result["response_type"] == "safe"
    assert result["assistance_case_id"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_officer_sees_ivr_reply_on_the_alert(db_conn, delivery_row):
    from httpx import ASGITransport, AsyncClient

    from services.api.auth import Principal, issue_access_token
    from services.api.main import app
    from services.api.rbac import OFFICER

    digit = await config_repo.get_str(db_conn, "ivr.dtmf.safe")
    await record_from_dtmf(db_conn, delivery_row["id"], digit)
    token, _ = await issue_access_token(
        db_conn,
        Principal(user_id=1, email="officer.a@setu.example", role=OFFICER, unit_scope_id=None),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(
            f"/api/v1/alerts/{delivery_row['alert_id']}/responses",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body
    assert body[0]["response_type"] == "safe"
    assert body[0]["channel_code"]
