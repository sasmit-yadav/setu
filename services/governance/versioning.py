from __future__ import annotations

from typing import Any

import asyncpg
from redis.asyncio import Redis

from services.api import config_repo
from services.audit.ledger import append_audit
from services.delivery.keys import keys
from services.delivery.state_machine import transition
from services.delivery.states import State


class VersionInFlightError(Exception):
    pass


async def create_new_version(
    conn: asyncpg.Connection,
    alert_id: int,
    *,
    change_reason: str,
    severity: str | None = None,
    headline: str | None = None,
    body: str | None = None,
    expires_at: Any = None,
) -> int:
    current = await conn.fetchrow(
        """
        SELECT id, incident_id, version_number, severity, headline, body, lang, area,
               effective_at, expires_at, source_id, lifecycle_status
        FROM alert WHERE id = $1
        """,
        alert_id,
    )
    if current is None:
        raise KeyError(alert_id)
    if current["lifecycle_status"] not in {"active", "draft", "superseded"}:
        raise ValueError("alert_not_versionable")
    new_id = await conn.fetchval(
        """
        INSERT INTO alert (
            external_id, source_id, severity, headline, body, lang, area,
            effective_at, expires_at, raw_checksum, incident_id,
            version_number, supersedes_alert_id, change_reason, lifecycle_status
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7,
            now(), $8, $9, $10,
            $11, $12, $13, 'draft'
        )
        RETURNING id
        """,
        f"{current['source_id']}-v{current['incident_id']}-{current['version_number'] + 1}",
        current["source_id"],
        severity or current["severity"],
        headline or current["headline"],
        body or current["body"],
        current["lang"],
        current["area"],
        expires_at if expires_at is not None else current["expires_at"],
        f"version-{current['incident_id']}-{current['version_number'] + 1}",
        current["incident_id"],
        current["version_number"] + 1,
        alert_id,
        change_reason,
    )
    await append_audit(
        conn,
        alert_id=new_id,
        incident_id=current["incident_id"],
        event_type="alert.version_created",
        payload={
            "supersedes_alert_id": alert_id,
            "version_number": current["version_number"] + 1,
            "change_reason": change_reason,
        },
        actor="api",
    )
    return int(new_id)


async def supersede_predecessor(
    conn: asyncpg.Connection,
    alert_id: int,
    *,
    actor: str,
) -> int | None:
    row = await conn.fetchrow(
        "SELECT supersedes_alert_id, incident_id, change_reason FROM alert WHERE id = $1",
        alert_id,
    )
    if row is None or row["supersedes_alert_id"] is None:
        return None
    old_id = int(row["supersedes_alert_id"])
    await conn.execute(
        "UPDATE alert SET lifecycle_status = 'superseded' WHERE id = $1",
        old_id,
    )
    if await config_repo.get_bool(conn, "versioning.cancel_inflight_on_supersede"):
        pending = await conn.fetch(
            """
            SELECT id FROM delivery
            WHERE alert_id = $1 AND state IN ('pending', 'queued')
            """,
            old_id,
        )
        for delivery in pending:
            await transition(
                conn,
                delivery["id"],
                State.expired,
                actor=actor,
                reason="superseded_by_version",
            )
    await append_audit(
        conn,
        alert_id=old_id,
        incident_id=row["incident_id"],
        event_type="alert.superseded",
        payload={
            "superseded_by": alert_id,
            "reason": row["change_reason"],
        },
        actor=actor,
    )
    return old_id


async def acquire_supersede_lock(redis: Redis, conn: asyncpg.Connection, incident_id: int) -> bool:
    lock_ms = await config_repo.get_int(conn, "versioning.supersede_lock_ms")
    return bool(
        await redis.set(
            keys.lock_supersede(incident_id),
            "1",
            nx=True,
            px=lock_ms,
        )
    )


async def release_supersede_lock(redis: Redis, incident_id: int) -> None:
    await redis.delete(keys.lock_supersede(incident_id))
