from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from services.api.main import app
from services.api.settings import settings


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _otp_ready(db_conn) -> bool:
    if not settings.phone_hash_pepper:
        return False
    table = await db_conn.fetchval(
        "SELECT to_regclass('citizen_otp_challenge')"
    )
    if table is None:
        return False
    for key, value, unit, note in (
        ("auth.citizen_otp_ttl_seconds", "300", "seconds", "test"),
        ("auth.citizen_otp_resend_seconds", "45", "seconds", "test"),
        ("auth.citizen_otp_max_attempts", "5", "tries", "test"),
        ("demo.citizen_phone", "9000000000", "phone", "test"),
        ("demo.citizen_otp", "246810", "otp", "test"),
    ):
        await db_conn.execute(
            """
            INSERT INTO app_config (key, value, unit, note)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (key) DO NOTHING
            """,
            key,
            value,
            unit,
            note,
        )
    user = await db_conn.fetchval(
        "SELECT id FROM app_user WHERE lower(email) = lower('citizen@setu.example')"
    )
    return user is not None


async def test_citizen_otp_demo_phone_issues_jwt(client, db_conn, monkeypatch):
    if not await _otp_ready(db_conn):
        pytest.skip("citizen OTP table/config/pepper not ready")
    monkeypatch.setattr("services.api.citizen_otp._twilio_ready", lambda: False)
    phone = await db_conn.fetchval(
        "SELECT value FROM app_config WHERE key = 'demo.citizen_phone'"
    )
    code = await db_conn.fetchval(
        "SELECT value FROM app_config WHERE key = 'demo.citizen_otp'"
    )
    asked = await client.post("/api/v1/auth/citizen/otp/request", json={"phone": phone})
    assert asked.status_code == 204
    res = await client.post(
        "/api/v1/auth/citizen/otp/verify",
        json={"phone": phone, "code": code},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["role"] == "citizen"
    assert body["access_token"]
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["role"] == "citizen"
    await db_conn.execute(
        "UPDATE refresh_token SET revoked_at = now() "
        "WHERE user_id = $1 AND revoked_at IS NULL",
        me.json()["user_id"],
    )


async def test_citizen_otp_wrong_code_is_401(client, db_conn, monkeypatch):
    if not await _otp_ready(db_conn):
        pytest.skip("citizen OTP table/config/pepper not ready")
    monkeypatch.setattr("services.api.citizen_otp._twilio_ready", lambda: False)
    phone = await db_conn.fetchval(
        "SELECT value FROM app_config WHERE key = 'demo.citizen_phone'"
    )
    asked = await client.post("/api/v1/auth/citizen/otp/request", json={"phone": phone})
    assert asked.status_code == 204
    res = await client.post(
        "/api/v1/auth/citizen/otp/verify",
        json={"phone": phone, "code": "000000"},
    )
    assert res.status_code == 401


async def test_two_village_phones_get_distinct_users_and_own_fcm(client, db_conn, monkeypatch):
    """Four Muttil SIMs must not collapse onto citizen@setu.example, and Enable
    alerts must write the FCM token onto that phone's recipient — not the
    one village citizen_pwa row."""
    if not await _otp_ready(db_conn):
        pytest.skip("citizen OTP table/config/pepper not ready")

    import uuid

    from services.api.auth import hash_token
    from services.api.citizen_otp import otp_email_for_digest
    from services.enrollment.phone_hash import normalize_phone_e164, phone_hash

    monkeypatch.setattr("services.api.citizen_otp._twilio_ready", lambda: False)

    async def fake_lang(_conn, _unit: int) -> str | None:
        return "ml"

    monkeypatch.setattr("services.api.routers.citizen.lang_for_unit", fake_lang)

    unit_id = await db_conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")

    phones = [
        f"+9198{uuid.uuid4().int % 100000000:08d}",
        f"+9198{uuid.uuid4().int % 100000000:08d}",
    ]
    rec_ids: list[int] = []
    emails: list[str] = []
    user_ids: list[int] = []
    tokens: list[str] = []

    try:
        for phone in phones:
            e164 = await normalize_phone_e164(db_conn, phone)
            digest = phone_hash(e164)
            rec_id = await db_conn.fetchval(
                """
                INSERT INTO recipient (unit_id, kind, phone_hash, consented_at, consent_source)
                VALUES ($1, 'citizen', $2, now(), 'test_otp_fcm')
                RETURNING id
                """,
                unit_id,
                digest,
            )
            rec_ids.append(int(rec_id))
            asked = await client.post(
                "/api/v1/auth/citizen/otp/request", json={"phone": phone}
            )
            assert asked.status_code == 204, asked.text
            await db_conn.execute(
                "UPDATE citizen_otp_challenge SET code_hash = $2 WHERE phone_hash = $1",
                digest,
                hash_token("111111"),
            )
            res = await client.post(
                "/api/v1/auth/citizen/otp/verify",
                json={"phone": phone, "code": "111111"},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["role"] == "citizen"
            assert body["email"] == otp_email_for_digest(digest)
            assert body["email"] != "citizen@setu.example"
            emails.append(body["email"])
            me = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {body['access_token']}"},
            )
            assert me.status_code == 200
            user_ids.append(int(me.json()["user_id"]))
            tokens.append(body["access_token"])

        assert user_ids[0] != user_ids[1]
        assert emails[0] != emails[1]

        pwa_before = await db_conn.fetchval(
            """
            SELECT push_token FROM recipient
            WHERE unit_id = $1 AND kind = 'citizen_pwa'
            """,
            unit_id,
        )
        bound = await client.post(
            "/api/v1/citizen/device",
            headers={"Authorization": f"Bearer {tokens[0]}"},
            json={"push_token": "otp-phone-fcm-token"},
        )
        assert bound.status_code == 200, bound.text
        assert bound.json()["recipient_id"] == rec_ids[0]
        stored = await db_conn.fetchval(
            "SELECT push_token FROM recipient WHERE id = $1", rec_ids[0]
        )
        assert stored == "otp-phone-fcm-token"
        other = await db_conn.fetchval(
            "SELECT push_token FROM recipient WHERE id = $1", rec_ids[1]
        )
        assert other is None
        pwa_after = await db_conn.fetchval(
            """
            SELECT push_token FROM recipient
            WHERE unit_id = $1 AND kind = 'citizen_pwa'
            """,
            unit_id,
        )
        assert pwa_after == pwa_before
    finally:
        if rec_ids:
            await db_conn.execute(
                "DELETE FROM citizen_otp_challenge WHERE phone_hash IN "
                "(SELECT phone_hash FROM recipient WHERE id = ANY($1::bigint[]))",
                rec_ids,
            )
        if user_ids:
            await db_conn.execute(
                "UPDATE refresh_token SET revoked_at = now() "
                "WHERE user_id = ANY($1::bigint[]) AND revoked_at IS NULL",
                user_ids,
            )
            await db_conn.execute(
                "DELETE FROM refresh_token WHERE user_id = ANY($1::bigint[])",
                user_ids,
            )
            await db_conn.execute(
                "DELETE FROM app_user WHERE id = ANY($1::bigint[])",
                user_ids,
            )
        if rec_ids:
            await db_conn.execute(
                "DELETE FROM recipient WHERE id = ANY($1::bigint[])",
                rec_ids,
            )
