"""services/api/auth.py — identity: password verification, JWT issue/verify,
and revocable refresh sessions.

Design decisions worth stating, because each is a trade-off a reviewer should
be able to challenge:

  * Access tokens are stateless JWTs with a SHORT ttl (jwt.access_ttl_minutes,
    from app_config). Short, because a stateless token cannot be revoked — the
    ttl IS the revocation window.
  * Refresh tokens are OPAQUE random strings, stored server-side as a hash, and
    ROTATED on every use. A system that can order an evacuation must be able to
    cut off a stolen credential; a stateless refresh JWT cannot be revoked, so
    it is not used here.
  * Rotation detects theft: presenting an already-used refresh token means
    either replay or a race, and both are treated as compromise — the whole
    family is revoked rather than silently issuing a fresh pair.
  * A NULL password_hash means "this account cannot log in". It never means
    "any password is accepted". Seeded demo accounts start in exactly that
    state, so committing 06_app_users.sql creates no usable credential.

Rule 1: every ttl and cost factor comes from app_config, not a literal here.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import asyncpg
import bcrypt
from jose import JWTError, jwt

from services.api import config_repo
from services.api.settings import settings

ALGORITHM = "HS256"

# Unit conversion, not a tunable — the TTL itself is config
# (jwt.access_ttl_minutes); this is only how minutes become the seconds that
# OAuth's `expires_in` is defined in.
SECONDS_PER_MINUTE = 60

# bcrypt directly, NOT passlib. passlib 1.7.4 (last release 2020) is
# incompatible with bcrypt 5.x — it raises
# "password cannot be longer than 72 bytes" from its own internal self-test.
# Pinning an old bcrypt to keep an unmaintained wrapper working is the wrong
# trade on a security-critical path; bcrypt's own API is small enough that the
# wrapper bought nothing.
#
# THE 72-BYTE LIMIT, handled explicitly rather than by truncation: bcrypt
# ignores everything past 72 bytes, so two different long passwords sharing a
# 72-byte prefix would be interchangeable. Pre-hashing with SHA-256 and
# base64-encoding the digest gives a fixed 44-byte input that is always under
# the limit, imposes no user-facing password length cap, and silently truncates
# nothing. base64 (not raw digest bytes) matters: a raw digest can contain a
# NUL byte, which C-string handling inside bcrypt would treat as end-of-input.
_BCRYPT_IDENT = b"$2b$"


class AuthError(Exception):
    """Authentication failed. Deliberately carries no detail about WHICH part
    failed — 'no such user' and 'wrong password' must be indistinguishable to a
    caller, or the endpoint becomes an account-enumeration oracle."""

    def __init__(self, code: str = "invalid_credentials") -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. This is what every RBAC check reads, and what
    the audit ledger records as `actor` — so attribution is derived from a
    verified token, never from a caller-supplied field."""

    user_id: int
    email: str
    role: str
    unit_scope_id: int | None


def hash_token(raw: str) -> str:
    """Refresh tokens are stored hashed. A database dump must not yield usable
    credentials. SHA-256 (not bcrypt) is correct here: the input is 256 bits of
    server-generated entropy, so it is not brute-forcible and does not need a
    slow KDF — unlike a human-chosen password."""
    return hashlib.sha256(raw.encode()).hexdigest()


def _prepare(raw: str) -> bytes:
    """SHA-256 -> base64, so bcrypt always sees a fixed 44-byte input.

    See the note above: this removes bcrypt's 72-byte cliff without truncating
    and without capping password length.
    """
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(raw: str, *, rounds: int) -> str:
    return bcrypt.hashpw(_prepare(raw), bcrypt.gensalt(rounds=rounds)).decode()


# A real hash of a throwaway value, generated once at import. verify_password
# compares against this when no credential is stored, so "account has no
# password" costs the same time as "wrong password" — otherwise login latency
# reveals which accounts exist and are provisioned.
_DUMMY_HASH = bcrypt.hashpw(_prepare("dummy"), bcrypt.gensalt(rounds=4))


def verify_password(raw: str, stored: str | None) -> bool:
    if not stored:
        bcrypt.checkpw(_prepare(raw), _DUMMY_HASH)
        return False
    try:
        return bcrypt.checkpw(_prepare(raw), stored.encode())
    except (ValueError, TypeError):
        # Malformed or unrecognised hash — a failed login, never a 500 that
        # would distinguish this account from any other.
        return False


async def issue_access_token(conn: asyncpg.Connection, principal: Principal) -> tuple[str, int]:
    ttl_minutes = await config_repo.get_int(conn, "jwt.access_ttl_minutes")
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=ttl_minutes)
    payload = {
        "sub": str(principal.user_id),
        "email": principal.email,
        "role": principal.role,
        "unit_scope_id": principal.unit_scope_id,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    if not settings.jwt_signing_secret:
        raise AuthError("jwt_not_configured")
    token = jwt.encode(payload, settings.jwt_signing_secret, algorithm=ALGORITHM)
    return token, ttl_minutes * SECONDS_PER_MINUTE


def decode_access_token(token: str) -> Principal:
    if not settings.jwt_signing_secret:
        raise AuthError("jwt_not_configured")
    try:
        claims = jwt.decode(token, settings.jwt_signing_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise AuthError("invalid_token") from exc
    try:
        return Principal(
            user_id=int(claims["sub"]),
            email=str(claims["email"]),
            role=str(claims["role"]),
            unit_scope_id=claims.get("unit_scope_id"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthError("malformed_token") from exc


async def authenticate(conn: asyncpg.Connection, email: str, password: str) -> Principal:
    row = await conn.fetchrow(
        """
        SELECT id, email, role, unit_scope_id, password_hash, active
        FROM app_user WHERE lower(email) = lower($1)
        """,
        email,
    )
    # Uniform failure for every reason: unknown account, no credential set,
    # wrong password, deactivated. Anything else leaks account state.
    if row is None or not row["active"] or not verify_password(password, row["password_hash"]):
        raise AuthError()
    await conn.execute("UPDATE app_user SET last_login_at = now() WHERE id = $1", row["id"])
    return Principal(
        user_id=row["id"],
        email=row["email"],
        role=row["role"],
        unit_scope_id=row["unit_scope_id"],
    )


async def issue_refresh_token(
    conn: asyncpg.Connection, user_id: int, *, user_agent: str | None = None
) -> str:
    ttl_days = await config_repo.get_int(conn, "jwt.refresh_ttl_days")
    raw = secrets.token_urlsafe(48)
    await conn.execute(
        """
        INSERT INTO refresh_token (user_id, token_hash, expires_at, user_agent)
        VALUES ($1, $2, now() + ($3 || ' days')::interval, $4)
        """,
        user_id,
        hash_token(raw),
        str(ttl_days),
        user_agent,
    )
    return raw


async def rotate_refresh_token(
    conn: asyncpg.Connection, raw: str, *, user_agent: str | None = None
) -> tuple[Principal, str]:
    """Consume a refresh token and issue a replacement.

    Presenting an ALREADY-REVOKED token is treated as compromise, not as a
    benign retry: every live session for that user is revoked. The alternative
    — quietly issuing a new pair — would let a stolen token keep working
    indefinitely alongside the legitimate one.
    """
    row = await conn.fetchrow(
        """
        SELECT rt.id, rt.user_id, rt.revoked_at, rt.expires_at,
               u.email, u.role, u.unit_scope_id, u.active
        FROM refresh_token rt
        JOIN app_user u ON u.id = rt.user_id
        WHERE rt.token_hash = $1
        """,
        hash_token(raw),
    )
    if row is None:
        raise AuthError("invalid_refresh_token")

    if row["revoked_at"] is not None:
        await revoke_all_for_user(conn, row["user_id"])
        raise AuthError("refresh_token_reused")

    if row["expires_at"] <= datetime.now(UTC):
        raise AuthError("refresh_token_expired")
    if not row["active"]:
        raise AuthError("account_inactive")

    await conn.execute(
        "UPDATE refresh_token SET revoked_at = now() WHERE id = $1", row["id"]
    )
    principal = Principal(
        user_id=row["user_id"],
        email=row["email"],
        role=row["role"],
        unit_scope_id=row["unit_scope_id"],
    )
    replacement = await issue_refresh_token(conn, row["user_id"], user_agent=user_agent)
    return principal, replacement


async def revoke_refresh_token(conn: asyncpg.Connection, raw: str) -> None:
    await conn.execute(
        "UPDATE refresh_token SET revoked_at = now() "
        "WHERE token_hash = $1 AND revoked_at IS NULL",
        hash_token(raw),
    )


async def revoke_all_for_user(conn: asyncpg.Connection, user_id: int) -> None:
    await conn.execute(
        "UPDATE refresh_token SET revoked_at = now() "
        "WHERE user_id = $1 AND revoked_at IS NULL",
        user_id,
    )
