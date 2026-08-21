"""services/api/rbac.py — Part 26's permission matrix, as FastAPI dependencies.

The spec says: "This table IS the spec for the FastAPI dependency, not prose
about it. One test per row, allow and deny." This module is that table.

Three roles carry the whole privacy design (§12.2), and each is expressed here
rather than left to a reviewer's memory:

  auditor     — sees PROOF the system behaved correctly, never the PII the
                system protects. Aggregate-only on /assistance: that a trapped
                case existed, its priority and response time — never its point
                geometry. An RTI applicant needs to prove the state responded;
                they do not need a map of which houses had someone trapped.
  relay_node  — NEVER sees individual assistance cases, at any scope. A relay
                operator gets a COUNT AND AN AREA ("twelve households in your
                ward could not be reached"), never names, numbers, or who asked
                for medical help. The obvious implementation hands them a list
                and leaks, to a semi-trusted community member, exactly who in
                the village called for help.
  citizen     — their own data only.

`require_role` is deliberately deny-by-default: a route with no explicit
dependency gets nothing, and an unknown role matches nothing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import asyncpg
from fastapi import Depends, Header, HTTPException, Request, status

from services.api.auth import AuthError, Principal, decode_access_token
from services.api.deps import get_conn

# ── the roles, exactly as seeded in 06_app_users.sql and constrained by §5.5 ──
CITIZEN = "citizen"
OFFICER = "officer"
STATE_ADMIN = "state_admin"
AUDITOR = "auditor"
RELAY_NODE = "relay_node"

ALL_ROLES = frozenset({CITIZEN, OFFICER, STATE_ADMIN, AUDITOR, RELAY_NODE})

# Roles that may compose, validate, approve, dispatch, or version an alert.
# state_admin is included everywhere officer is, per Part 26's matrix.
ALERT_WRITE_ROLES = frozenset({OFFICER, STATE_ADMIN})
# Roles that may READ operational detail (deliveries, assurance, audit,
# incidents, analytics). Auditor is included: reading proof is its purpose.
OPERATIONAL_READ_ROLES = frozenset({OFFICER, STATE_ADMIN, AUDITOR})


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "unauthenticated", "code": "missing_or_invalid_token"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(code: str = "role") -> HTTPException:
    # 403, not 404: the caller IS authenticated, they simply lack the role.
    # Part 10's status-code contract keeps these distinguishable so the
    # frontend can tell "log in again" from "you cannot do this".
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": "forbidden", "code": code},
    )


async def current_principal(
    request: Request,
    authorization: str | None = Header(default=None),
) -> Principal:
    """Resolve the caller from a Bearer token. Raises 401 if absent/invalid.

    The resulting Principal is the ONLY acceptable source of actor identity —
    `approver_id`, `assigned_by` and the audit ledger's `actor` all read from
    here. Before this existed, POST /alerts/{id}/approve took approver_id from
    the request body, which made Four-Eyes bypassable by typing a different
    number.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthenticated()
    token = authorization.split(" ", 1)[1].strip()
    try:
        principal = decode_access_token(token)
    except AuthError as exc:
        raise _unauthenticated() from exc
    request.state.principal = principal
    return principal


async def optional_principal(
    request: Request,
    authorization: str | None = Header(default=None),
) -> Principal | None:
    """For endpoints that are public but behave differently when authenticated
    (e.g. /methodology, /units public aggregate)."""
    if not authorization:
        return None
    try:
        return await current_principal(request, authorization)
    except HTTPException:
        return None


def require_role(*roles: str) -> Callable[..., Awaitable[Principal]]:
    """Dependency factory. Deny-by-default: only the named roles pass."""
    allowed = frozenset(roles)
    if not allowed <= ALL_ROLES:
        raise ValueError(f"unknown role(s): {sorted(allowed - ALL_ROLES)}")

    async def _dependency(
        principal: Principal = Depends(current_principal),
    ) -> Principal:
        if principal.role not in allowed:
            raise _forbidden("role")
        return principal

    return _dependency


async def assert_unit_in_scope(
    conn: asyncpg.Connection, principal: Principal, unit_id: int
) -> None:
    """Officers are scoped to their own district (Part 26's '(own district)'
    qualifier). state_admin and auditor are national.

    A NULL unit_scope_id on an officer means unscoped — which is correct for
    the seeded demo accounts and for a single-district deployment, but is
    recorded here so nobody reads the absence of a check as an oversight.
    """
    if principal.role in (STATE_ADMIN, AUDITOR):
        return
    if principal.unit_scope_id is None:
        return
    if principal.unit_scope_id == unit_id:
        return
    # Scope covers the officer's own unit and everything beneath it, so a
    # district officer can act on the villages inside their district.
    within = await conn.fetchval(
        """
        WITH RECURSIVE descendants AS (
            SELECT id FROM admin_unit WHERE id = $1
            UNION ALL
            SELECT u.id FROM admin_unit u JOIN descendants d ON u.parent_id = d.id
        )
        SELECT EXISTS (SELECT 1 FROM descendants WHERE id = $2)
            OR EXISTS (
                SELECT 1
                FROM admin_unit scope
                JOIN admin_unit target ON target.id = $2
                WHERE scope.id = $1
                  AND ST_Intersects(scope.geom, target.geom)
            )
        """,
        principal.unit_scope_id,
        unit_id,
    )
    if not within:
        raise _forbidden("unit_scope")


async def assert_alert_in_scope(
    conn: asyncpg.Connection, principal: Principal, alert_id: int
) -> None:
    """Scope an alert by whether it intersects the officer's unit at all."""
    if principal.role in (STATE_ADMIN, AUDITOR):
        return
    if principal.unit_scope_id is None:
        return
    intersects = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1 FROM alert a
            JOIN admin_unit u ON u.id = $2
            WHERE a.id = $1 AND ST_Intersects(a.area, u.geom)
        )
        """,
        alert_id,
        principal.unit_scope_id,
    )
    if not intersects:
        raise _forbidden("unit_scope")


async def assert_delivery_in_scope(
    conn: asyncpg.Connection, principal: Principal, delivery_id: int
) -> None:
    unit_id = await conn.fetchval(
        """
        SELECT r.unit_id FROM delivery d
        JOIN recipient r ON r.id = d.recipient_id
        WHERE d.id = $1
        """,
        delivery_id,
    )
    if unit_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery_not_found")
    await assert_unit_in_scope(conn, principal, int(unit_id))


# ── convenience dependencies, named after Part 26's columns ──
require_officer = require_role(OFFICER, STATE_ADMIN)
require_state_admin = require_role(STATE_ADMIN)
require_operational_read = require_role(OFFICER, STATE_ADMIN, AUDITOR)
require_assistance_read = require_role(OFFICER, STATE_ADMIN, AUDITOR)
require_citizen_write = require_role(CITIZEN, OFFICER, STATE_ADMIN, RELAY_NODE)
require_relay_summary = require_role(OFFICER, STATE_ADMIN, AUDITOR, RELAY_NODE)
require_relay_confirm = require_role(OFFICER, STATE_ADMIN, RELAY_NODE)
require_alert_read = require_role(CITIZEN, OFFICER, STATE_ADMIN, AUDITOR)
require_models_read = require_role(STATE_ADMIN, AUDITOR)
require_any_authenticated = require_role(*sorted(ALL_ROLES))


async def conn_and_officer(
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_officer),
) -> tuple[asyncpg.Connection, Principal]:
    return conn, principal
