from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg

from services.api import config_repo
from services.api.settings import settings
from services.audit.ledger import append_audit
from services.crypto.alert_signing import sign_payload
from services.ingestion.incident_linker import link_to_incident
from services.ml.translate import ensure_translations


class ComposeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def create_draft_alert(
    conn: asyncpg.Connection,
    *,
    severity: str,
    headline: str,
    body: str,
    lang: str,
    unit_ids: list[int] | None = None,
    geojson: dict[str, Any] | None = None,
    point_lon: float | None = None,
    point_lat: float | None = None,
    effective_at: datetime | None = None,
    expires_at: datetime | None = None,
    estimated_onset_at: datetime | None = None,
    actor: str = "officer",
) -> dict[str, Any]:
    effective = effective_at or datetime.now(UTC)
    expires = expires_at

    external_id = f"manual-{uuid.uuid4()}"
    checksum = hashlib.sha256(f"{headline}|{body}|{external_id}".encode()).hexdigest()

    if geojson is not None:
        alert_id = await conn.fetchval(
            """
            INSERT INTO alert (
                external_id, source_id, severity, headline, body, lang, area,
                effective_at, expires_at, raw_checksum, lifecycle_status, estimated_onset_at
            )
            VALUES (
                $1, 'manual', $2, $3, $4, $5,
                ST_Multi(ST_CollectionExtract(
                    ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON($6), 4326)),
                    3
                )),
                $7, $8, $9, 'draft', $10
            )
            RETURNING id
            """,
            external_id,
            severity,
            headline,
            body,
            lang,
            json.dumps(geojson),
            effective,
            expires,
            checksum,
            estimated_onset_at,
        )
    elif unit_ids:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM admin_unit WHERE id = ANY($1::bigint[])",
            unit_ids,
        )
        if count != len(unit_ids):
            raise ComposeError("unit_not_found", "One or more unit_ids do not exist")
        alert_id = await conn.fetchval(
            """
            INSERT INTO alert (
                external_id, source_id, severity, headline, body, lang, area,
                effective_at, expires_at, raw_checksum, lifecycle_status, estimated_onset_at
            )
            SELECT
                $1, 'manual', $2, $3, $4, $5,
                ST_Multi(ST_Union(u.geom)),
                $6, $7, $8, 'draft', $9
            FROM admin_unit u
            WHERE u.id = ANY($10::bigint[])
            RETURNING id
            """,
            external_id,
            severity,
            headline,
            body,
            lang,
            effective,
            expires,
            checksum,
            estimated_onset_at,
            unit_ids,
        )
    elif point_lon is not None and point_lat is not None:
        radius_km = await config_repo.get_float(conn, "alert.manual.default_radius_km")
        km_to_m = await config_repo.get_float(conn, "geo.km_to_meters")
        radius_m = radius_km * km_to_m
        alert_id = await conn.fetchval(
            """
            INSERT INTO alert (
                external_id, source_id, severity, headline, body, lang, area,
                effective_at, expires_at, raw_checksum, lifecycle_status, estimated_onset_at
            )
            VALUES (
                $1, 'manual', $2, $3, $4, $5,
                ST_Multi(ST_Buffer(
                    ST_SetSRID(ST_MakePoint($6, $7), 4326)::geography,
                    $8
                )::geometry),
                $9, $10, $11, 'draft', $12
            )
            RETURNING id
            """,
            external_id,
            severity,
            headline,
            body,
            lang,
            point_lon,
            point_lat,
            radius_m,
            effective,
            expires,
            checksum,
            estimated_onset_at,
        )
    else:
        raise ComposeError("area_required", "Provide unit_ids, geojson, or point coordinates")

    incident_id = await link_to_incident(conn, int(alert_id), actor=actor)
    if settings.alert_signing_seed_b64:
        sign_body = {
            "alert_id": int(alert_id),
            "headline": headline,
            "severity": severity,
            "effective_at": effective.isoformat(),
        }
        signature = sign_payload(sign_body)
        await conn.execute(
            "UPDATE alert SET signature = decode($1, 'base64') WHERE id = $2",
            signature,
            alert_id,
        )
    await append_audit(
        conn,
        alert_id=int(alert_id),
        incident_id=incident_id,
        event_type="alert.created",
        payload={"severity": severity, "source_id": "manual"},
        actor=actor,
    )
    await ensure_translations(conn, int(alert_id))
    target_count = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT r.id)
        FROM recipient r
        JOIN admin_unit u ON u.id = r.unit_id
        JOIN alert a ON a.id = $1
        WHERE ST_Intersects(u.geom, a.area)
          AND r.consented_at IS NOT NULL
          AND r.opted_out_at IS NULL
        """,
        alert_id,
    )
    return {
        "alert_id": int(alert_id),
        "incident_id": incident_id,
        "target_count": int(target_count or 0),
        "lifecycle_status": "draft",
    }


async def preview_exposure(conn: asyncpg.Connection, alert_id: int) -> dict[str, Any]:
    exists = await conn.fetchval("SELECT 1 FROM alert WHERE id = $1", alert_id)
    if not exists:
        raise ComposeError("alert_not_found", "Alert not found")
    rows = await conn.fetch(
        """
        SELECT u.id, u.name, u.population, u.building_count,
               COUNT(DISTINCT r.id) AS recipients
        FROM admin_unit u
        JOIN alert a ON a.id = $1
        LEFT JOIN recipient r ON r.unit_id = u.id
          AND r.consented_at IS NOT NULL AND r.opted_out_at IS NULL
        WHERE ST_Intersects(u.geom, a.area)
        GROUP BY u.id, u.name, u.population, u.building_count
        ORDER BY recipients DESC, u.name
        """,
        alert_id,
    )
    total = sum(int(row["recipients"] or 0) for row in rows)
    population = sum(int(row["population"] or 0) for row in rows)
    buildings = sum(int(row["building_count"] or 0) for row in rows)
    return {
        "alert_id": alert_id,
        "recipient_count": total,
        "estimated_population": population or None,
        "building_count": buildings or None,
        "units": [
            {
                "unit_id": row["id"],
                "name": row["name"],
                "recipients": int(row["recipients"] or 0),
                "estimated_population": int(row["population"]) if row["population"] is not None else None,
                "building_count": int(row["building_count"]) if row["building_count"] is not None else None,
            }
            for row in rows
        ],
    }


async def patch_draft_alert(
    conn: asyncpg.Connection,
    alert_id: int,
    *,
    expires_at: datetime | None = None,
    headline: str | None = None,
    body: str | None = None,
    severity: str | None = None,
    actor: str = "officer",
) -> dict[str, Any]:
    current = await conn.fetchrow(
        "SELECT id, lifecycle_status, incident_id FROM alert WHERE id = $1",
        alert_id,
    )
    if current is None:
        raise ComposeError("alert_not_found", "Alert not found")
    if current["lifecycle_status"] != "draft":
        raise ComposeError("not_draft", "Only draft alerts can be edited")
    await conn.execute(
        """
        UPDATE alert
        SET expires_at = COALESCE($2, expires_at),
            headline = COALESCE($3, headline),
            body = COALESCE($4, body),
            severity = COALESCE($5, severity)
        WHERE id = $1
        """,
        alert_id,
        expires_at,
        headline,
        body,
        severity,
    )
    await append_audit(
        conn,
        alert_id=alert_id,
        incident_id=current["incident_id"],
        event_type="alert.patched",
        payload={"expires_at": expires_at.isoformat() if expires_at else None},
        actor=actor,
    )
    await ensure_translations(conn, int(alert_id))
    return await preview_exposure(conn, alert_id)
