"""Part 26's permission matrix, as tests — "one test per row, allow and deny."

These are deliberately written against the ASGI app rather than against the
dependency functions directly: the thing being asserted is that a real HTTP
request without the right role cannot reach the handler. Testing
`require_officer` in isolation would pass even if a router forgot to depend
on it, which is exactly the mistake this file exists to catch.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from services.api.auth import Principal, decode_access_token, issue_access_token
from services.api.main import app
from services.api.rbac import (
    AUDITOR,
    CITIZEN,
    OFFICER,
    RELAY_NODE,
    STATE_ADMIN,
    require_role,
)


async def _token(db_conn, role: str, *, user_id: int = 1, unit_scope_id: int | None = None) -> str:
    principal = Principal(
        user_id=user_id,
        email=f"{role}@setu.example",
        role=role,
        unit_scope_id=unit_scope_id,
    )
    token, _ = await issue_access_token(db_conn, principal)
    return token


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── the token itself ───────────────────────────────────────────────────────

async def test_access_token_round_trips_role_and_scope(db_conn):
    token = await _token(db_conn, OFFICER, user_id=42, unit_scope_id=7)
    principal = decode_access_token(token)
    assert principal.user_id == 42
    assert principal.role == OFFICER
    assert principal.unit_scope_id == 7


async def test_tampered_token_is_rejected(db_conn):
    from services.api.auth import AuthError

    token = await _token(db_conn, OFFICER)
    # Flip a character in the signature segment.
    head, payload, sig = token.split(".")
    tampered = f"{head}.{payload}.{'A' if sig[0] != 'A' else 'B'}{sig[1:]}"
    with pytest.raises(AuthError):
        decode_access_token(tampered)


async def test_role_escalation_by_editing_payload_is_rejected(db_conn):
    """The whole point of signing: a citizen cannot rewrite their own role."""
    import base64
    import json

    from services.api.auth import AuthError

    token = await _token(db_conn, CITIZEN)
    head, payload, sig = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    claims["role"] = STATE_ADMIN
    forged_payload = base64.urlsafe_b64encode(
        json.dumps(claims).encode()
    ).decode().rstrip("=")
    with pytest.raises(AuthError):
        decode_access_token(f"{head}.{forged_payload}.{sig}")


def test_require_role_rejects_unknown_role_at_definition_time():
    """A typo in a role name must fail loudly when the dependency is built,
    not silently deny every request at runtime."""
    with pytest.raises(ValueError):
        require_role("offcier")  # deliberate typo


# ── the matrix: dispatch is the one that matters most ──────────────────────

@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 404),      # allowed through RBAC; 404 because the alert id is fake
        (STATE_ADMIN, 404),  # allowed
        (CITIZEN, 403),
        (AUDITOR, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_dispatch_requires_officer(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.post(
        "/api/v1/alerts/99999999/dispatch",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code}"


async def test_dispatch_without_token_is_401(client):
    r = await client.post("/api/v1/alerts/99999999/dispatch")
    assert r.status_code == 401


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 404),
        (STATE_ADMIN, 404),
        (CITIZEN, 403),
        (AUDITOR, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_approve_requires_officer(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.post(
        "/api/v1/alerts/99999999/approve",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code}"


async def test_approver_id_cannot_be_supplied_by_the_caller(client, db_conn):
    """F3's Four-Eyes is only real if the approver is the AUTHENTICATED user.

    Sending approver_id must be rejected outright (422), not silently ignored —
    a client that thinks it is approving as someone else should be told it is
    wrong.
    """
    token = await _token(db_conn, OFFICER)
    r = await client.post(
        "/api/v1/alerts/99999999/approve",
        headers={"Authorization": f"Bearer {token}"},
        json={"approver_id": 999},
    )
    assert r.status_code == 422
    assert "approver_id" in r.text


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 200),
        (STATE_ADMIN, 200),
        (AUDITOR, 200),      # reading proof is the auditor's entire purpose
        (CITIZEN, 200),
        (RELAY_NODE, 403),
    ],
)
async def test_alert_list_read_roles(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.get(
        "/api/v1/alerts?limit=1", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == expected, f"{role} -> {r.status_code}"


@pytest.mark.parametrize("role", [CITIZEN, OFFICER, AUDITOR, RELAY_NODE, STATE_ADMIN])
async def test_me_works_for_every_role(client, db_conn, role):
    token = await _token(db_conn, role)
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["role"] == role


# ── endpoints that must stay public ────────────────────────────────────────

async def test_health_is_public(client):
    assert (await client.get("/health")).status_code == 200


async def test_public_config_is_public(client):
    """The citizen PWA fetches its config BEFORE anyone logs in — if this ever
    starts requiring auth, the offline-first app cannot bootstrap."""
    assert (await client.get("/api/v1/public/config")).status_code == 200


async def test_receipt_is_nonce_gated_not_role_gated(client):
    r = await client.post(
        "/api/v1/deliveries/99999999/receipt",
        json={"receipt_nonce": "unused", "event_type": "device_delivered"},
    )
    assert r.status_code in (403, 404)


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 200),
        (STATE_ADMIN, 200),
        (AUDITOR, 200),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_assistance_list_roles(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.get(
        "/api/v1/assistance?limit=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code} {r.text}"


async def test_assistance_without_token_is_401(client):
    assert (await client.get("/api/v1/assistance")).status_code == 401


async def test_relay_node_never_sees_assistance_cases(client, db_conn):
    token = await _token(db_conn, RELAY_NODE)
    headers = {"Authorization": f"Bearer {token}"}
    listed = await client.get("/api/v1/assistance", headers=headers)
    assert listed.status_code == 403
    detail = await client.get("/api/v1/assistance/1", headers=headers)
    assert detail.status_code == 403
    assigned = await client.post(
        "/api/v1/assistance/1/assign",
        headers=headers,
        json={"assigned_team": "rescue"},
    )
    assert assigned.status_code == 403
    summary = await client.get("/api/v1/assistance/summary", headers=headers)
    assert summary.status_code == 200


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 404),
        (STATE_ADMIN, 404),
        (AUDITOR, 403),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_assistance_assign_requires_officer(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.post(
        "/api/v1/assistance/99999999/assign",
        headers={"Authorization": f"Bearer {token}"},
        json={"assigned_team": "rescue"},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code} {r.text}"


async def test_assigned_by_cannot_be_supplied_by_the_caller(client, db_conn):
    token = await _token(db_conn, OFFICER)
    r = await client.post(
        "/api/v1/assistance/99999999/assign",
        headers={"Authorization": f"Bearer {token}"},
        json={"assigned_team": "rescue", "assigned_by": 999},
    )
    assert r.status_code == 422
    assert "assigned_by" in r.text


async def test_auditor_assistance_omits_point_geometry(client, db_conn, delivery_row):
    from services.response.citizen_response import submit_response

    result = await submit_response(
        db_conn,
        delivery_id=delivery_row["id"],
        response_type="trapped",
        idempotency_key="rbac-geo-1",
        location=(76.13, 11.65),
        location_consent=True,
    )
    case_id = result["assistance_case_id"]
    assert case_id is not None

    officer = await _token(db_conn, OFFICER)
    officer_view = await client.get(
        f"/api/v1/assistance/{case_id}",
        headers={"Authorization": f"Bearer {officer}"},
    )
    assert officer_view.status_code == 200
    body = officer_view.json()
    assert body["citizen_response_id"] is not None
    assert body["lat"] == pytest.approx(11.65, abs=0.001)
    assert body["lon"] == pytest.approx(76.13, abs=0.001)

    auditor = await _token(db_conn, AUDITOR)
    auditor_view = await client.get(
        f"/api/v1/assistance/{case_id}",
        headers={"Authorization": f"Bearer {auditor}"},
    )
    assert auditor_view.status_code == 200
    stripped = auditor_view.json()
    assert stripped["id"] == case_id
    assert stripped["priority_score"] is not None
    assert stripped["citizen_response_id"] is None
    assert stripped["lat"] is None
    assert stripped["lon"] is None
    assert stripped["free_text"] is None


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 404),
        (STATE_ADMIN, 404),
        (AUDITOR, 404),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_incident_read_roles(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.get(
        "/api/v1/incidents/99999999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code}"


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 404),
        (STATE_ADMIN, 404),
        (AUDITOR, 404),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_unit_reachability_roles(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.get(
        "/api/v1/units/99999999/reachability",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code}"


async def test_officer_scope_covers_contained_village(client, db_conn):
    parent = await db_conn.fetchrow(
        "SELECT id FROM admin_unit WHERE name = 'Vythiri' AND level = 3"
    )
    child = await db_conn.fetchrow(
        "SELECT id FROM admin_unit WHERE name = 'Muttil North' AND level = 5"
    )
    if parent is None or child is None:
        pytest.skip("demo geometry not loaded")
    token = await _token(db_conn, OFFICER, unit_scope_id=int(parent["id"]))
    headers = {"Authorization": f"Bearer {token}"}
    allowed = await client.get(
        f"/api/v1/units/{int(child['id'])}/reachability",
        headers=headers,
    )
    assert allowed.status_code == 200, allowed.text
    outsider = await db_conn.fetchval(
        """
        SELECT u.id FROM admin_unit u
        WHERE u.level = 5
          AND NOT ST_Intersects(u.geom, (SELECT geom FROM admin_unit WHERE id = $1))
        LIMIT 1
        """,
        parent["id"],
    )
    if outsider is None:
        pytest.skip("no out-of-scope village to deny")
    denied = await client.get(
        f"/api/v1/units/{int(outsider)}/reachability",
        headers=headers,
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "unit_scope"


async def test_officer_assistance_lists_contained_village(client, db_conn):
    """Help needed must use geom intersection, not parent_id (always NULL)."""
    import uuid

    from services.response.citizen_response import submit_response

    parent = await db_conn.fetchrow(
        "SELECT id FROM admin_unit WHERE name = 'Vythiri' AND level = 3"
    )
    child = await db_conn.fetchrow(
        "SELECT id FROM admin_unit WHERE name = 'Muttil North' AND level = 5"
    )
    if parent is None or child is None:
        pytest.skip("demo geometry not loaded")

    recipient_id = await db_conn.fetchval(
        """
        INSERT INTO recipient (unit_id, kind, preferred_lang, consented_at)
        VALUES ($1, 'citizen', 'en', now())
        RETURNING id
        """,
        child["id"],
    )
    incident_id = await db_conn.fetchval(
        """
        INSERT INTO incident (label, incident_type, status, origin_source)
        VALUES ('SCOPE-HELP', 'test', 'active', 'manual')
        RETURNING id
        """
    )
    alert_id = await db_conn.fetchval(
        """
        INSERT INTO alert (
            source_id, severity, headline, body, lang, area,
            effective_at, expires_at, raw_checksum, incident_id, lifecycle_status
        )
        SELECT 'manual', 'extreme', 'Help scope', 'Body', 'en', geom,
               now(), now() + interval '1 hour', $3, $1, 'active'
        FROM admin_unit WHERE id = $2
        RETURNING id
        """,
        incident_id,
        child["id"],
        f"scope-help-{uuid.uuid4()}",
    )
    channel_id = await db_conn.fetchval("SELECT id FROM channel WHERE code = 'sim'")
    delivery_id = await db_conn.fetchval(
        """
        INSERT INTO delivery (alert_id, recipient_id, channel_id, state)
        VALUES ($1, $2, $3, 'delivered')
        RETURNING id
        """,
        alert_id,
        recipient_id,
        channel_id,
    )
    result = await submit_response(
        db_conn,
        delivery_id=int(delivery_id),
        response_type="trapped",
        idempotency_key=f"scope-help-{uuid.uuid4()}",
    )
    assert result["assistance_case_id"] is not None

    token = await _token(db_conn, OFFICER, unit_scope_id=int(parent["id"]))
    listed = await client.get(
        "/api/v1/assistance?status=all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200, listed.text
    ids = {row["unit_id"] for row in listed.json()}
    assert int(child["id"]) in ids


async def test_unit_risk_is_public_aggregate_except_relay(client, db_conn):
    public = await client.get("/api/v1/units/99999999/risk")
    assert public.status_code == 404
    relay = await _token(db_conn, RELAY_NODE)
    denied = await client.get(
        "/api/v1/units/99999999/risk",
        headers={"Authorization": f"Bearer {relay}"},
    )
    assert denied.status_code == 403
    citizen = await _token(db_conn, CITIZEN)
    allowed = await client.get(
        "/api/v1/units/99999999/risk",
        headers={"Authorization": f"Bearer {citizen}"},
    )
    assert allowed.status_code == 404


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 422),
        (STATE_ADMIN, 422),
        (AUDITOR, 403),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_enrollment_import_requires_officer(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.post(
        "/api/v1/admin/recipients/import",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("x.csv", b"phone\n", "text/csv")},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code} {r.text}"


@pytest.mark.parametrize(
    "role,expected",
    [
        (CITIZEN, 404),
        (OFFICER, 404),
        (STATE_ADMIN, 404),
        (RELAY_NODE, 404),
        (AUDITOR, 403),
    ],
)
async def test_ack_and_citizen_delivery_roles(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    headers = {"Authorization": f"Bearer {token}"}
    ack = await client.post(
        "/api/v1/ack",
        headers={**headers, "Idempotency-Key": "rbac-ack"},
        json={"delivery_id": 99999999},
    )
    assert ack.status_code == expected, f"ack {role} -> {ack.status_code}"
    delivery = await client.get("/api/v1/citizen/deliveries/99999999", headers=headers)
    assert delivery.status_code == expected, f"delivery {role} -> {delivery.status_code}"


async def test_citizen_inbox_returns_list(client, db_conn):
    token = await _token(db_conn, CITIZEN)
    r = await client.get(
        "/api/v1/citizen/deliveries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_auditor_cannot_list_citizen_inbox(client, db_conn):
    token = await _token(db_conn, AUDITOR)
    r = await client.get(
        "/api/v1/citizen/deliveries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


async def test_ack_without_token_is_401(client):
    r = await client.post(
        "/api/v1/ack",
        headers={"Idempotency-Key": "no-token"},
        json={"delivery_id": 1},
    )
    assert r.status_code == 401


async def test_methodology_is_public(client):
    r = await client.get("/api/v1/methodology")
    assert r.status_code == 200
    body = r.json()
    assert "channel_capability" in body
    assert body["channel_capability"]


async def test_incidents_list_requires_operational_read(client, db_conn):
    denied = await client.get("/api/v1/incidents")
    assert denied.status_code == 401
    citizen = await _token(db_conn, CITIZEN)
    forbidden = await client.get(
        "/api/v1/incidents",
        headers={"Authorization": f"Bearer {citizen}"},
    )
    assert forbidden.status_code == 403
    officer = await _token(db_conn, OFFICER)
    allowed = await client.get(
        "/api/v1/incidents",
        headers={"Authorization": f"Bearer {officer}"},
    )
    assert allowed.status_code == 200


async def test_board_requires_operational_read(client, db_conn):
    denied = await client.get("/api/v1/incidents/99999999/board")
    assert denied.status_code == 401
    citizen = await _token(db_conn, CITIZEN)
    forbidden = await client.get(
        "/api/v1/incidents/99999999/board",
        headers={"Authorization": f"Bearer {citizen}"},
    )
    assert forbidden.status_code == 403
    officer = await _token(db_conn, OFFICER)
    missing = await client.get(
        "/api/v1/incidents/99999999/board",
        headers={"Authorization": f"Bearer {officer}"},
    )
    assert missing.status_code == 404


async def test_ops_summary_and_feed_require_officer(client, db_conn):
    denied = await client.get("/api/v1/ops/summary")
    assert denied.status_code == 401
    citizen = await _token(db_conn, CITIZEN)
    forbidden = await client.get(
        "/api/v1/ops/summary",
        headers={"Authorization": f"Bearer {citizen}"},
    )
    assert forbidden.status_code == 403
    token = await _token(db_conn, OFFICER)
    summary = await client.get("/api/v1/ops/summary", headers={"Authorization": f"Bearer {token}"})
    assert summary.status_code == 200
    feed = await client.get("/api/v1/ops/feed", headers={"Authorization": f"Bearer {token}"})
    assert feed.status_code == 200
    assert isinstance(feed.json(), list)
    replies = await client.get("/api/v1/ops/replies", headers={"Authorization": f"Bearer {token}"})
    assert replies.status_code == 200
    assert isinstance(replies.json(), list)
    mapped = await client.get("/api/v1/ops/map", headers={"Authorization": f"Bearer {token}"})
    assert mapped.status_code == 200


async def test_lead_time_requires_operational_read(client, db_conn):
    citizen = await _token(db_conn, CITIZEN)
    denied = await client.get(
        "/api/v1/analytics/lead-time",
        headers={"Authorization": f"Bearer {citizen}"},
    )
    assert denied.status_code == 403
    officer = await _token(db_conn, OFFICER)
    allowed = await client.get(
        "/api/v1/analytics/lead-time",
        headers={"Authorization": f"Bearer {officer}"},
    )
    assert allowed.status_code == 200


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 422),
        (STATE_ADMIN, 422),
        (AUDITOR, 403),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_compose_requires_officer(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.post(
        "/api/v1/alerts",
        headers={"Authorization": f"Bearer {token}"},
        json={"severity": "severe", "headline": "x", "body": "y", "lang": "en"},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code} {r.text}"


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 404),
        (STATE_ADMIN, 404),
        (AUDITOR, 403),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_preview_and_validate_require_officer(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    headers = {"Authorization": f"Bearer {token}"}
    preview = await client.post("/api/v1/alerts/99999999/preview", headers=headers)
    assert preview.status_code == expected, f"preview {role} -> {preview.status_code}"
    validate = await client.post("/api/v1/alerts/99999999/validate", headers=headers)
    assert validate.status_code == expected, f"validate {role} -> {validate.status_code}"


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 404),
        (STATE_ADMIN, 404),
        (AUDITOR, 403),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_new_version_requires_officer(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.post(
        "/api/v1/alerts/99999999/new-version",
        headers={"Authorization": f"Bearer {token}"},
        json={"change_reason": "escalate"},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code}"


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 404),
        (STATE_ADMIN, 404),
        (AUDITOR, 404),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_deliveries_assurance_audit_pdf_roles(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    headers = {"Authorization": f"Bearer {token}"}
    for path in (
        "/api/v1/alerts/99999999/deliveries",
        "/api/v1/alerts/99999999/assurance",
        "/api/v1/alerts/99999999/responses",
        "/api/v1/alerts/99999999/audit",
        "/api/v1/alerts/99999999/report.pdf",
    ):
        r = await client.get(path, headers=headers)
        assert r.status_code == expected, f"{path} {role} -> {r.status_code}"


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 404),
        (STATE_ADMIN, 404),
        (AUDITOR, 404),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_after_action_roles(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.get(
        "/api/v1/incidents/99999999/after-action",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code}"


@pytest.mark.parametrize(
    "role,expected",
    [
        (STATE_ADMIN, 404),
        (OFFICER, 403),
        (AUDITOR, 403),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_close_incident_requires_state_admin(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.post(
        "/api/v1/incidents/99999999/close",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code}"


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 200),
        (STATE_ADMIN, 200),
        (AUDITOR, 200),
        (RELAY_NODE, 200),
        (CITIZEN, 403),
    ],
)
async def test_relay_tasks_roles(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.get(
        "/api/v1/relay/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code} {r.text}"


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 404),
        (STATE_ADMIN, 404),
        (RELAY_NODE, 404),
        (AUDITOR, 403),
        (CITIZEN, 403),
    ],
)
async def test_relay_task_confirm_roles(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.post(
        "/api/v1/relay/tasks/99999999/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code}"


@pytest.mark.parametrize(
    "role,expected",
    [
        (STATE_ADMIN, 200),
        (AUDITOR, 200),
        (OFFICER, 403),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_models_roles(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.get("/api/v1/models", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == expected, f"{role} -> {r.status_code} {r.text}"


async def test_methodology_allows_relay_node(client, db_conn):
    token = await _token(db_conn, RELAY_NODE)
    r = await client.get("/api/v1/methodology", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


async def test_units_list_public_except_relay(client, db_conn):
    public = await client.get("/api/v1/units?limit=1")
    assert public.status_code == 200
    relay = await _token(db_conn, RELAY_NODE)
    denied = await client.get(
        "/api/v1/units",
        headers={"Authorization": f"Bearer {relay}"},
    )
    assert denied.status_code == 403


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 404),
        (STATE_ADMIN, 404),
        (AUDITOR, 403),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_assistance_patch_requires_officer(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.patch(
        "/api/v1/assistance/99999999",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "assigned"},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code} {r.text}"


async def test_timeline_requires_operational_read(client, db_conn):
    citizen = await _token(db_conn, CITIZEN)
    denied = await client.get(
        "/api/v1/incidents/99999999/timeline",
        headers={"Authorization": f"Bearer {citizen}"},
    )
    assert denied.status_code == 403
    officer = await _token(db_conn, OFFICER)
    missing = await client.get(
        "/api/v1/incidents/99999999/timeline",
        headers={"Authorization": f"Bearer {officer}"},
    )
    assert missing.status_code == 404


# ── rows that had no allow/deny pair ────────────────────────────────────────
# Part 26 lists /units/{id}/vulnerability and POST /response as their own rows,
# and Day 10's DoD is "every row has an allow test and a deny test". Both were
# missing entirely, as was the citizen device-registration endpoint added for
# live FCM. A router that forgot its role dependency on any of these would not
# have been caught by any existing test.


@pytest.mark.parametrize(
    "role,expected",
    [
        (OFFICER, 404),
        (STATE_ADMIN, 404),
        (AUDITOR, 404),
        (CITIZEN, 403),
        (RELAY_NODE, 403),
    ],
)
async def test_unit_vulnerability_roles(client, db_conn, role, expected):
    token = await _token(db_conn, role)
    r = await client.get(
        "/api/v1/units/99999999/vulnerability",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == expected, f"{role} -> {r.status_code}"


@pytest.mark.parametrize(
    "role,allowed",
    [
        (CITIZEN, True),
        (OFFICER, True),
        (STATE_ADMIN, True),
        (RELAY_NODE, True),
        (AUDITOR, False),
    ],
)
async def test_response_write_roles(client, db_conn, role, allowed):
    """C6's write path. Part 26 gives auditor ❌ here — an auditor proving the
    state responded must never be able to author a citizen's response."""
    token = await _token(db_conn, role)
    r = await client.post(
        "/api/v1/response",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "rbac-probe"},
        json={
            "delivery_id": 99999999,
            "response_type": "safe",
            "free_text": None,
            "lat": None,
            "lon": None,
            "location_consent": False,
        },
    )
    if allowed:
        assert r.status_code != 403, f"{role} should not be forbidden -> {r.text}"
    else:
        assert r.status_code == 403, f"{role} -> {r.status_code}"


@pytest.mark.parametrize(
    "role,allowed",
    [
        (CITIZEN, True),
        (OFFICER, True),
        (STATE_ADMIN, True),
        (RELAY_NODE, True),
        (AUDITOR, False),
    ],
)
async def test_citizen_device_registration_roles(client, db_conn, role, allowed):
    """Push-token registration rides the same citizen-write role set as /ack and
    /response, so an auditor token must not be able to bind a device."""
    token = await _token(db_conn, role, unit_scope_id=None)
    r = await client.post(
        "/api/v1/citizen/device",
        headers={"Authorization": f"Bearer {token}"},
        json={"push_token": "rbac-probe-token"},
    )
    if allowed:
        # 400 = no unit scope on this synthetic principal, which is the handler
        # being reached. Only 403 would mean the role gate rejected it.
        assert r.status_code != 403, f"{role} should not be forbidden -> {r.text}"
    else:
        assert r.status_code == 403, f"{role} -> {r.status_code}"


async def test_unauthenticated_cannot_register_a_device(client):
    r = await client.post("/api/v1/citizen/device", json={"push_token": "no-auth"})
    assert r.status_code in (401, 403), r.status_code


async def test_device_register_stores_village_lang(client, db_conn, monkeypatch):
    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")

    async def fake_lang(_conn, scoped_unit: int) -> str | None:
        assert scoped_unit == unit_id
        return "ml"

    monkeypatch.setattr("services.api.routers.citizen.lang_for_unit", fake_lang)
    token = await _token(db_conn, CITIZEN, unit_scope_id=int(unit_id))
    try:
        r = await client.post(
            "/api/v1/citizen/device",
            headers={"Authorization": f"Bearer {token}"},
            json={"push_token": "village-lang-token"},
        )
        assert r.status_code == 200, r.text
        preferred = await db_conn.fetchval(
            """
            SELECT preferred_lang FROM recipient
            WHERE unit_id = $1 AND kind = 'citizen_pwa'
            """,
            unit_id,
        )
        assert preferred == "ml"
    finally:
        await db_conn.execute(
            """
            DELETE FROM recipient
            WHERE unit_id = $1 AND kind = 'citizen_pwa'
              AND push_token = 'village-lang-token'
            """,
            unit_id,
        )
