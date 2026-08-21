from __future__ import annotations

import asyncpg

from services.api import config_repo
from services.audit.ledger import append_audit
from services.ingestion.incident_linker import link_to_incident
from services.ingestion.types import ParsedAlert
from services.ml.dedup import assign_cluster, next_cluster_id
from services.ml.reach_risk import predict_for_alert
from services.ml.translate import ensure_translations


async def upsert_alert(conn: asyncpg.Connection, parsed: ParsedAlert) -> int:
    cluster_id = parsed.cluster_id
    if cluster_id is None:
        cluster_id = await assign_cluster(conn, parsed)
        if cluster_id is None:
            cluster_id = await next_cluster_id(conn)
    radius_m = None
    if parsed.geometry_wkt is None:
        radius_km = await config_repo.get_float(conn, f"ingest.{parsed.source_id}.alert_radius_km")
        km_to_m = await config_repo.get_float(conn, "geo.km_to_meters")
        radius_m = radius_km * km_to_m
    alert_id = await conn.fetchval(
        """
        INSERT INTO alert (
            external_id, source_id, severity, headline, body, lang, area,
            effective_at, expires_at, raw_checksum, etag, cluster_id,
            lifecycle_status, estimated_onset_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6,
            CASE
              WHEN $7::text IS NOT NULL THEN ST_SetSRID(ST_GeomFromGeoJSON($7), 4326)
              ELSE ST_Multi(ST_Buffer(
                ST_SetSRID(ST_MakePoint($8, $9), 4326)::geography,
                $10
              )::geometry)
            END,
            $11, $12, $13, $14, $15, 'draft', $16
        )
        ON CONFLICT (source_id, external_id) DO UPDATE SET
            severity = EXCLUDED.severity,
            headline = EXCLUDED.headline,
            body = EXCLUDED.body,
            expires_at = EXCLUDED.expires_at,
            raw_checksum = EXCLUDED.raw_checksum,
            etag = EXCLUDED.etag,
            estimated_onset_at = EXCLUDED.estimated_onset_at,
            cluster_id = COALESCE(EXCLUDED.cluster_id, alert.cluster_id)
        RETURNING id
        """,
        parsed.external_id,
        parsed.source_id,
        parsed.severity,
        parsed.headline,
        parsed.body,
        parsed.lang,
        parsed.geometry_wkt,
        parsed.lon,
        parsed.lat,
        radius_m,
        parsed.effective_at,
        parsed.expires_at,
        parsed.raw_checksum,
        parsed.etag,
        cluster_id,
        parsed.estimated_onset_at,
    )
    incident_id = await link_to_incident(
        conn,
        int(alert_id),
        cluster_id=cluster_id,
        actor="ingestion",
    )
    await append_audit(
        conn,
        alert_id=alert_id,
        incident_id=incident_id,
        event_type="alert.ingested",
        payload={"source_id": parsed.source_id, "external_id": parsed.external_id},
        actor="ingestion",
    )
    await predict_for_alert(conn, int(alert_id))
    await ensure_translations(conn, int(alert_id))
    return int(alert_id)
