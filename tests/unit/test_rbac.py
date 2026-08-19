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
        (CITIZEN, 403),
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
