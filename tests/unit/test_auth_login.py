from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from services.api import config_repo
from services.api.auth import hash_password
from services.api.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_login_rejects_wrong_password(client, db_conn):
    row = await db_conn.fetchrow(
        "SELECT id FROM app_user WHERE lower(email) = lower($1)",
        "citizen@setu.example",
    )
    if row is None:
        pytest.skip("seed users missing")
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "citizen@setu.example", "password": "not-the-password"},
    )
    assert res.status_code == 401


async def test_login_issues_citizen_jwt(client, db_conn):
    row = await db_conn.fetchrow(
        "SELECT id, password_hash FROM app_user WHERE lower(email) = lower($1)",
        "citizen@setu.example",
    )
    if row is None:
        pytest.skip("seed users missing")
    rounds = await config_repo.get_int(db_conn, "auth.bcrypt_rounds")
    password = "setu-test-login-only"
    await db_conn.execute(
        "UPDATE app_user SET password_hash = $1 WHERE id = $2",
        hash_password(password, rounds=rounds),
        row["id"],
    )
    try:
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": "citizen@setu.example", "password": password},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["role"] == "citizen"
        assert body["access_token"]
        assert body["refresh_token"]
        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json()["email"] == "citizen@setu.example"
        assert me.json()["role"] == "citizen"
    finally:
        await db_conn.execute(
            "UPDATE app_user SET password_hash = $1 WHERE id = $2",
            row["password_hash"],
            row["id"],
        )
        await db_conn.execute(
            "UPDATE refresh_token SET revoked_at = now() "
            "WHERE user_id = $1 AND revoked_at IS NULL",
            row["id"],
        )
