from __future__ import annotations

import asyncpg

from services.api import config_repo


class ApprovalError(Exception):
    def __init__(self, code: str, detail: dict[str, int | str]) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


async def required_count(conn: asyncpg.Connection, severity: str) -> int:
    key = f"approval.required.{severity.lower()}"
    value = await config_repo.get(conn, key)
    if value is None:
        raise KeyError(key)
    return int(value)


async def approval_count(conn: asyncpg.Connection, alert_id: int) -> int:
    return int(
        await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM alert_approval
            WHERE alert_id = $1 AND decision = 'approved'
            """,
            alert_id,
        )
        or 0
    )


async def is_authoritative_source(conn: asyncpg.Connection, alert_id: int) -> bool:
    auto = await config_repo.get_bool(conn, "approval.authoritative_sources_auto_approve")
    if not auto:
        return False
    return bool(
        await conn.fetchval(
            """
            SELECT s.is_authoritative
            FROM alert a
            JOIN alert_source s ON s.source_id = a.source_id
            WHERE a.id = $1
            """,
            alert_id,
        )
    )


async def record_auto_approval(conn: asyncpg.Connection, alert_id: int) -> None:
    exists = await conn.fetchval(
        """
        SELECT 1 FROM alert_approval
        WHERE alert_id = $1 AND provenance = 'authoritative_source'
        """,
        alert_id,
    )
    if exists:
        return
    await conn.execute(
        """
        INSERT INTO alert_approval (alert_id, approver_id, provenance, decision)
        VALUES ($1, NULL, 'authoritative_source', 'approved')
        """,
        alert_id,
    )


async def approve(
    conn: asyncpg.Connection,
    alert_id: int,
    approver_id: int,
    *,
    reason: str | None = None,
) -> int:
    await conn.execute(
        """
        INSERT INTO alert_approval (alert_id, approver_id, provenance, decision, reason)
        VALUES ($1, $2, 'human', 'approved', $3)
        ON CONFLICT (alert_id, approver_id) DO NOTHING
        """,
        alert_id,
        approver_id,
        reason,
    )
    return await approval_count(conn, alert_id)


async def ensure_dispatch_allowed(conn: asyncpg.Connection, alert_id: int) -> None:
    if await is_authoritative_source(conn, alert_id):
        await record_auto_approval(conn, alert_id)
        return
    severity = await conn.fetchval("SELECT severity FROM alert WHERE id = $1", alert_id)
    if severity is None:
        raise ValueError(f"alert {alert_id} not found")
    need = await required_count(conn, severity)
    have = await approval_count(conn, alert_id)
    if have < need:
        raise ApprovalError(
            "approval_required",
            {"have": have, "need": need},
        )
