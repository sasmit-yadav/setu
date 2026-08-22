"""Citizen PWA login: Indian mobile + OTP.

Officers stay on email/password. Citizens prove a number. The same
phone_hash used for SMS enrollment is the lookup key, so REGISTER / CSV
import / this screen cannot create three people from one SIM.

When Twilio is configured the code is random and SMSed. When it is not,
only the seeded demo number can complete verify — using demo.citizen_otp —
so a missing SMS credential cannot become an open login for every number.
"""

from __future__ import annotations

import asyncio
import logging
import secrets

import asyncpg

from services.api import config_repo
from services.api.auth import AuthError, Principal, hash_token
from services.api.settings import settings
from services.enrollment.phone_hash import normalize_phone_e164, phone_hash

log = logging.getLogger(__name__)

CITIZEN_ROLE = "citizen"
OTP_EMAIL_DOMAIN = "otp.setu.invalid"


def otp_email_for_digest(digest: bytes) -> str:
    return f"c{digest.hex()}@{OTP_EMAIL_DOMAIN}"


def digest_hex_from_otp_email(email: str) -> str | None:
    local, _, domain = email.partition("@")
    if domain != OTP_EMAIL_DOMAIN or not local.startswith("c"):
        return None
    hexpart = local[1:]
    if len(hexpart) != 64:
        return None
    return hexpart


def _twilio_ready() -> bool:
    return bool(
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_from_number
    )


async def _same_number(conn: asyncpg.Connection, left: str, right: str) -> bool:
    a = await normalize_phone_e164(conn, left)
    b = await normalize_phone_e164(conn, right)
    return a == b


async def request_otp(conn: asyncpg.Connection, phone_raw: str) -> None:
    e164 = await normalize_phone_e164(conn, phone_raw)
    digest = phone_hash(e164)
    ttl = await config_repo.get_int(conn, "auth.citizen_otp_ttl_seconds")
    resend = await config_repo.get_int(conn, "auth.citizen_otp_resend_seconds")

    existing = await conn.fetchrow(
        """
        SELECT created_at
        FROM citizen_otp_challenge
        WHERE phone_hash = $1 AND expires_at > now()
        """,
        digest,
    )
    if existing is not None:
        age = await conn.fetchval("SELECT EXTRACT(EPOCH FROM (now() - $1))", existing["created_at"])
        if age is not None and float(age) < resend:
            return

    demo_phone = await config_repo.get_str(conn, "demo.citizen_phone")
    is_demo = await _same_number(conn, e164, demo_phone)
    if _twilio_ready():
        code = f"{secrets.randbelow(1_000_000):06d}"
    elif is_demo:
        code = (await config_repo.get_str(conn, "demo.citizen_otp")).strip()
    else:
        code = f"{secrets.randbelow(1_000_000):06d}"

    await conn.execute(
        """
        INSERT INTO citizen_otp_challenge (phone_hash, code_hash, attempts, expires_at)
        VALUES ($1, $2, 0, now() + ($3 || ' seconds')::interval)
        ON CONFLICT (phone_hash) DO UPDATE
            SET code_hash = EXCLUDED.code_hash,
                attempts = 0,
                expires_at = EXCLUDED.expires_at,
                created_at = now()
        """,
        digest,
        hash_token(code),
        str(ttl),
    )

    if _twilio_ready():
        await _send_otp_sms(e164, code)


async def _send_otp_sms(e164: str, code: str) -> None:
    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    def _send() -> None:
        client.messages.create(
            to=e164,
            from_=settings.twilio_from_number,
            body=f"SETU login code: {code}. Valid a few minutes. Do not share it.",
        )

    try:
        await asyncio.to_thread(_send)
    except Exception:
        # Same outward result as a successful request — do not become an
        # oracle for "this number exists" or "Twilio is down".
        log.exception("citizen OTP SMS failed")


async def verify_otp(conn: asyncpg.Connection, phone_raw: str, code_raw: str) -> Principal:
    e164 = await normalize_phone_e164(conn, phone_raw)
    digest = phone_hash(e164)
    offered = "".join(ch for ch in code_raw.strip() if ch.isdigit())
    max_tries = await config_repo.get_int(conn, "auth.citizen_otp_max_attempts")

    row = await conn.fetchrow(
        """
        SELECT code_hash, attempts
        FROM citizen_otp_challenge
        WHERE phone_hash = $1 AND expires_at > now()
        """,
        digest,
    )
    if row is None:
        await conn.execute("DELETE FROM citizen_otp_challenge WHERE phone_hash = $1", digest)
        raise AuthError()
    if int(row["attempts"]) >= max_tries:
        await conn.execute("DELETE FROM citizen_otp_challenge WHERE phone_hash = $1", digest)
        raise AuthError()
    if hash_token(offered) != row["code_hash"]:
        await conn.execute(
            """
            UPDATE citizen_otp_challenge
            SET attempts = attempts + 1
            WHERE phone_hash = $1
            """,
            digest,
        )
        raise AuthError()

    principal = await _principal_for_phone(conn, digest, e164)
    await conn.execute("DELETE FROM citizen_otp_challenge WHERE phone_hash = $1", digest)
    await conn.execute("UPDATE app_user SET last_login_at = now() WHERE id = $1", principal.user_id)
    return principal


async def _principal_for_phone(
    conn: asyncpg.Connection, digest: bytes, e164: str
) -> Principal:
    demo_phone = await config_repo.get_str(conn, "demo.citizen_phone")
    if await _same_number(conn, e164, demo_phone):
        demo_email = await config_repo.get_str(conn, "demo.citizen_email")
        row = await conn.fetchrow(
            """
            SELECT id, email, role, unit_scope_id, active
            FROM app_user WHERE lower(email) = lower($1)
            """,
            demo_email,
        )
        if row is None or not row["active"] or row["role"] != CITIZEN_ROLE:
            raise AuthError()
        return Principal(
            user_id=row["id"],
            email=row["email"],
            role=row["role"],
            unit_scope_id=row["unit_scope_id"],
        )

    rec = await conn.fetchrow(
        """
        SELECT unit_id
        FROM recipient
        WHERE phone_hash = $1
          AND consented_at IS NOT NULL
          AND opted_out_at IS NULL
        ORDER BY id
        LIMIT 1
        """,
        digest,
    )
    if rec is None:
        raise AuthError()
    unit_id = int(rec["unit_id"])
    email = otp_email_for_digest(digest)
    existing = await conn.fetchrow(
        """
        SELECT id, email, role, unit_scope_id, active
        FROM app_user
        WHERE lower(email) = lower($1)
        """,
        email,
    )
    if existing is not None:
        if not existing["active"] or existing["role"] != CITIZEN_ROLE:
            raise AuthError()
        if int(existing["unit_scope_id"] or 0) != unit_id:
            await conn.execute(
                "UPDATE app_user SET unit_scope_id = $2 WHERE id = $1",
                existing["id"],
                unit_id,
            )
        return Principal(
            user_id=int(existing["id"]),
            email=existing["email"],
            role=existing["role"],
            unit_scope_id=unit_id,
        )
    created = await conn.fetchrow(
        """
        INSERT INTO app_user (email, role, unit_scope_id, active)
        VALUES ($1, $2, $3, true)
        ON CONFLICT (email) DO UPDATE SET
            role = EXCLUDED.role,
            unit_scope_id = EXCLUDED.unit_scope_id,
            active = true
        RETURNING id, email, role, unit_scope_id
        """,
        email,
        CITIZEN_ROLE,
        unit_id,
    )
    if created is None:
        raise AuthError()
    return Principal(
        user_id=created["id"],
        email=created["email"],
        role=created["role"],
        unit_scope_id=created["unit_scope_id"],
    )


async def recipient_id_for_principal(
    conn: asyncpg.Connection, principal: Principal
) -> int | None:
    hexpart = digest_hex_from_otp_email(principal.email)
    if hexpart is None:
        return None
    return await conn.fetchval(
        "SELECT id FROM recipient WHERE phone_hash = decode($1, 'hex') LIMIT 1",
        hexpart,
    )
