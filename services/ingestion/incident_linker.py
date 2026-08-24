from __future__ import annotations

import asyncpg

from services.audit.ledger import append_audit


async def generate_label(conn: asyncpg.Connection, alert_id: int, incident_type: str) -> str:
    # Label prefix = the name of the COARSEST admin unit the alert overlaps
    # most (ADM3 sub-district before ADM5 village), giving human-readable
    # labels like WAYANAD-FLOOD-001 rather than a village nobody recognises.
    #
    # This previously read COALESCE(u.state_code, u.name) — admin_unit has no
    # state_code column and never has (see migration 0001), so live USGS
    # ingestion died with UndefinedColumnError while fixture-based unit tests
    # never hit this path. Ordering by level ASC is what recovers the intended
    # "prefer the wider region" behaviour without the phantom column.
    unit = await conn.fetchrow(
        """
        SELECT u.name AS prefix
        FROM admin_unit u
        JOIN alert a ON a.id = $1
        WHERE ST_Intersects(u.geom, a.area)
        ORDER BY u.level ASC,
                 ST_Area(ST_Intersection(u.geom, a.area)) DESC
        LIMIT 1
        """,
        alert_id,
    )
    prefix = (unit["prefix"] if unit else "SETU").upper().replace(" ", "-")[:12]
    hazard = incident_type.upper().replace(" ", "-")[:20]
    seq = await conn.fetchval(
        """
        SELECT COUNT(*) + 1 FROM incident WHERE label LIKE $1
        """,
        f"{prefix}-{hazard}-%",
    )
    return f"{prefix}-{hazard}-{int(seq):03d}"


async def link_to_incident(
    conn: asyncpg.Connection,
    alert_id: int,
    *,
    cluster_id: int | None = None,
    actor: str = "ingestion",
) -> int:
    existing_incident = await conn.fetchval(
        "SELECT incident_id FROM alert WHERE id = $1",
        alert_id,
    )
    if existing_incident is not None:
        return int(existing_incident)

    if cluster_id is not None:
        cluster_incident = await conn.fetchval(
            """
            SELECT incident_id FROM alert
            WHERE cluster_id = $1 AND incident_id IS NOT NULL
            LIMIT 1
            """,
            cluster_id,
        )
        if cluster_incident is not None:
            await conn.execute(
                "UPDATE alert SET incident_id = $1 WHERE id = $2",
                cluster_incident,
                alert_id,
            )
            return int(cluster_incident)

    overlapping = await conn.fetchval(
        """
        SELECT i.id
        FROM incident i
        JOIN alert a ON a.id = $1
        JOIN alert a2 ON a2.incident_id = i.id
        WHERE a2.lifecycle_status = 'draft'
          AND NOT EXISTS (
            SELECT 1 FROM alert live
            WHERE live.incident_id = i.id
              AND live.lifecycle_status = 'active'
          )
          AND ST_Intersects(a.area, a2.area)
          AND a.effective_at <= COALESCE(a2.expires_at, a2.effective_at + interval '1 day')
          AND a2.effective_at <= COALESCE(a.expires_at, a2.effective_at + interval '1 day')
        ORDER BY i.opened_at DESC
        LIMIT 1
        """,
        alert_id,
    )
    if overlapping is not None:
        await conn.execute(
            "UPDATE alert SET incident_id = $1 WHERE id = $2",
            overlapping,
            alert_id,
        )
        return int(overlapping)

    alert = await conn.fetchrow(
        "SELECT source_id FROM alert WHERE id = $1",
        alert_id,
    )
    if alert is None:
        raise KeyError(alert_id)
    label = await generate_label(conn, alert_id, alert["source_id"])
    incident_id = await conn.fetchval(
        """
        INSERT INTO incident (label, incident_type, status, origin_source)
        VALUES ($1, $2, 'active', $3)
        RETURNING id
        """,
        label,
        alert["source_id"],
        alert["source_id"],
    )
    await conn.execute(
        "UPDATE alert SET incident_id = $1 WHERE id = $2",
        incident_id,
        alert_id,
    )
    await append_audit(
        conn,
        alert_id=alert_id,
        incident_id=incident_id,
        event_type="incident.opened",
        payload={"label": label},
        actor=actor,
    )
    return int(incident_id)


async def detach_if_incident_already_live(
    conn: asyncpg.Connection, alert_id: int, *, actor: str
) -> int | None:
    """A fresh compose must not share an incident with a warning already live.

    link_to_incident used to cluster overlapping Muttil drafts onto the same
    incident as an *active* send. Dispatch then hit
    alert_one_active_per_incident_uix and the API returned 500. Versions still
    share an incident via supersedes_alert_id; those go through
    supersede_predecessor instead.
    """
    row = await conn.fetchrow(
        """
        SELECT incident_id, supersedes_alert_id, source_id
        FROM alert WHERE id = $1
        """,
        alert_id,
    )
    if row is None or row["incident_id"] is None:
        return None
    if row["supersedes_alert_id"] is not None:
        return None
    blocker = await conn.fetchval(
        """
        SELECT id FROM alert
        WHERE incident_id = $1 AND id <> $2 AND lifecycle_status = 'active'
        """,
        row["incident_id"],
        alert_id,
    )
    if blocker is None:
        return None
    source = str(row["source_id"] or "manual")
    label = await generate_label(conn, alert_id, source)
    new_id = int(
        await conn.fetchval(
            """
            INSERT INTO incident (label, incident_type, status, origin_source)
            VALUES ($1, $2, 'active', $3)
            RETURNING id
            """,
            label,
            source,
            source,
        )
    )
    await conn.execute(
        "UPDATE alert SET incident_id = $1 WHERE id = $2",
        new_id,
        alert_id,
    )
    await append_audit(
        conn,
        alert_id=alert_id,
        incident_id=new_id,
        event_type="incident.opened",
        payload={
            "label": label,
            "split_from": int(row["incident_id"]),
            "blocked_by": int(blocker),
        },
        actor=actor,
    )
    return new_id
