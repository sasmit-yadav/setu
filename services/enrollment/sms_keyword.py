from __future__ import annotations

from dataclasses import dataclass

import asyncpg
from redis.asyncio import Redis

from services.api import config_repo
from services.api.settings import settings
from services.audit.ledger import append_audit
from services.enrollment.phone_hash import (
    PhoneNumberError,
    normalize_phone_e164,
    phone_hash,
)
from services.response.citizen_response import ResponseError, submit_response


@dataclass(frozen=True)
class SmsKeywordResult:
    action: str
    reply_text: str
    recipient_id: int | None = None


class SmsKeywordError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def _rate_limit(redis: Redis, conn: asyncpg.Connection, sender: str, limit: int) -> bool:
    key = f"setu:enrollment:sms:{sender}"
    count = await redis.incr(key)
    if count == 1:
        window = await config_repo.get_int(conn, "enrollment.sms_rate_window_seconds")
        await redis.expire(key, window)
    return count <= limit


async def _encrypt_phone(conn: asyncpg.Connection, phone_e164: str) -> bytes | None:
    if not settings.pgcrypto_sym_key:
        return None
    return await conn.fetchval(
        "SELECT pgp_sym_encrypt($1, $2)",
        phone_e164,
        settings.pgcrypto_sym_key,
    )


async def _default_unit(conn: asyncpg.Connection) -> int | None:
    return await conn.fetchval("SELECT id FROM admin_unit ORDER BY id LIMIT 1")


async def handle_inbound(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    from_number: str,
    body: str,
) -> SmsKeywordResult:
    if not settings.phone_hash_pepper:
        raise SmsKeywordError("enrollment_not_configured", "PHONE_HASH_PEPPER missing")
    limit = await config_repo.get_int(conn, "enrollment.sms_rate_limit_per_minute")
    if not await _rate_limit(redis, conn, from_number, limit):
        raise SmsKeywordError("rate_limited", "Too many inbound messages")
    register_kw = (await config_repo.get_str(conn, "enrollment.sms_keyword_register")).upper()
    stop_kw = (await config_repo.get_str(conn, "enrollment.sms_keyword_stop")).upper()
    token = body.strip().upper()
    try:
        phone_e164 = await normalize_phone_e164(conn, from_number)
    except PhoneNumberError as exc:
        # Twilio sends E.164, so this is a spoofed or malformed callback rather
        # than a real handset. Refuse it as bad input; never a 500 on a webhook.
        raise SmsKeywordError("invalid_sender", str(exc)) from exc
    digest = phone_hash(phone_e164)
    if token == stop_kw:
        reply = await config_repo.get_str(conn, "enrollment.sms_auto_reply_stopped")
        row = await conn.fetchrow(
            "SELECT id FROM recipient WHERE phone_hash = $1",
            digest,
        )
        if row:
            await conn.execute(
                "UPDATE recipient SET opted_out_at = now() WHERE id = $1",
                row["id"],
            )
            await append_audit(
                conn,
                event_type="enrollment.sms_stop",
                payload={"recipient_id": row["id"]},
                actor="sms_keyword",
            )
            return SmsKeywordResult("stop", reply, int(row["id"]))
        return SmsKeywordResult("stop_unknown", reply)
    first = token.split()[0] if token else ""
    ack = await _try_alert_ack(conn, digest, first)
    if ack is not None:
        return ack
    if token != register_kw:
        hint = await config_repo.get(conn, "response.sms_reply.hint")
        return SmsKeywordResult("unknown", hint or "SETU: Reply SAFE or HELP.")
    reply = await config_repo.get_str(conn, "enrollment.sms_auto_reply_registered")
    existing = await conn.fetchrow(
        "SELECT id, opted_out_at FROM recipient WHERE phone_hash = $1",
        digest,
    )
    if existing:
        if existing["opted_out_at"] is not None:
            await conn.execute(
                """
                UPDATE recipient
                SET opted_out_at = NULL, consented_at = now(), consent_source = 'sms_keyword'
                WHERE id = $1
                """,
                existing["id"],
            )
            await append_audit(
                conn,
                event_type="enrollment.sms_re_register",
                payload={"recipient_id": existing["id"]},
                actor="sms_keyword",
            )
        return SmsKeywordResult("already_registered", reply, int(existing["id"]))
    unit_id = await _default_unit(conn)
    if unit_id is None:
        raise SmsKeywordError("no_units", "No admin units loaded")
    phone_enc = await _encrypt_phone(conn, phone_e164)
    recipient_id = await conn.fetchval(
        """
        INSERT INTO recipient (
            unit_id, kind, phone_enc, phone_hash, preferred_lang,
            consented_at, consent_source
        )
        VALUES ($1, 'citizen', $2, $3, 'en', now(), 'sms_keyword')
        RETURNING id
        """,
        unit_id,
        phone_enc,
        digest,
    )
    await append_audit(
        conn,
        event_type="enrollment.sms_register",
        payload={"recipient_id": recipient_id},
        actor="sms_keyword",
    )
    return SmsKeywordResult("register", reply, int(recipient_id))


async def _try_alert_ack(
    conn: asyncpg.Connection, digest: str, token: str
) -> SmsKeywordResult | None:
    """SAFE / HELP on the latest live warning for this number."""
    safe_kw = (await config_repo.get(conn, "response.sms_keyword.safe") or "SAFE").upper()
    help_kw = (await config_repo.get(conn, "response.sms_keyword.help") or "HELP").upper()
    if token not in {safe_kw, help_kw}:
        return None
    row = await conn.fetchrow(
        """
        SELECT d.id
        FROM delivery d
        JOIN recipient r ON r.id = d.recipient_id
        JOIN alert a ON a.id = d.alert_id
        WHERE r.phone_hash = $1
          AND a.lifecycle_status = 'active'
          AND a.expires_at > now()
        ORDER BY d.id DESC
        LIMIT 1
        """,
        digest,
    )
    if row is None:
        reply = await config_repo.get(conn, "response.sms_reply.no_alert")
        return SmsKeywordResult(
            "no_alert",
            reply or "SETU: No live warning for this number.",
        )
    try:
        if token == safe_kw:
            await submit_response(
                conn,
                delivery_id=int(row["id"]),
                response_type="safe",
                idempotency_key=f"sms-safe-{row['id']}",
            )
            reply = await config_repo.get(conn, "response.sms_reply.safe")
            return SmsKeywordResult("safe", reply or "SETU: Marked safe. Thank you.")
        await submit_response(
            conn,
            delivery_id=int(row["id"]),
            response_type="other",
            idempotency_key=f"sms-help-{row['id']}",
            free_text="SMS: HELP",
        )
        reply = await config_repo.get(conn, "response.sms_reply.help")
        return SmsKeywordResult("help", reply or "SETU: Help request received.")
    except ResponseError as exc:
        raise SmsKeywordError(exc.code, exc.message) from exc
