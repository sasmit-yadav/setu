from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import asyncpg

from services.api import config_repo
from services.ingestion.types import ParsedAlert, QuarantineAlert, RawAlert


async def _mag_severity(conn: asyncpg.Connection, magnitude: float) -> str:
    if magnitude >= await config_repo.get_float(conn, "ingest.usgs.mag_extreme"):
        return "extreme"
    if magnitude >= await config_repo.get_float(conn, "ingest.usgs.mag_severe"):
        return "severe"
    if magnitude >= await config_repo.get_float(conn, "ingest.usgs.mag_moderate"):
        return "moderate"
    return "minor"


async def _default_expires(conn: asyncpg.Connection, effective_at: datetime) -> datetime:
    hours = await config_repo.get_int(conn, "ingest.alert_default_ttl_hours")
    return effective_at + timedelta(hours=hours)


async def parse_usgs(conn: asyncpg.Connection, raw: RawAlert) -> ParsedAlert:
    feature = json.loads(raw.body)
    props = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        raise QuarantineAlert("no_geometry", "USGS feature missing coordinates")
    magnitude = props.get("mag")
    if magnitude is None:
        raise QuarantineAlert("missing_magnitude", "USGS feature missing mag")
    effective_at = datetime.fromtimestamp(
        props["time"] / await config_repo.get_float(conn, "ingest.usgs.time_ms_divisor"),
        tz=UTC,
    )
    lon, lat = float(coords[0]), float(coords[1])
    return ParsedAlert(
        external_id=str(feature.get("id")),
        source_id="usgs",
        severity=await _mag_severity(conn, float(magnitude)),
        headline=str(props.get("title") or props.get("place") or "Earthquake"),
        body=str(props.get("place") or props.get("title") or "Earthquake detected"),
        lang="en",
        lon=lon,
        lat=lat,
        effective_at=effective_at,
        expires_at=await _default_expires(conn, effective_at),
        estimated_onset_at=None,
        raw_checksum=raw.checksum,
        etag=raw.etag,
    )


async def _gdacs_severity(conn: asyncpg.Connection, alertlevel: str) -> str:
    level = alertlevel.lower()
    if level == "red":
        return "extreme"
    if level == "orange":
        return "severe"
    if level == "green":
        return "moderate"
    return "minor"


async def parse_gdacs(
    conn: asyncpg.Connection,
    identifier: str,
    raw: RawAlert,
    metadata: dict,
) -> ParsedAlert:
    fromdate = metadata.get("fromdate")
    todate = metadata.get("todate")
    if not fromdate:
        raise QuarantineAlert("missing_effective_at", "GDACS event missing fromdate")
    effective_at = datetime.fromisoformat(fromdate.replace("Z", "+00:00"))
    if effective_at.tzinfo is None:
        effective_at = effective_at.replace(tzinfo=UTC)
    expires_at = (
        datetime.fromisoformat(todate.replace("Z", "+00:00")).replace(tzinfo=UTC)
        if todate
        else await _default_expires(conn, effective_at)
    )
    onset = effective_at
    geometry = json.loads(raw.body)
    geom_type = geometry.get("type")
    if geom_type == "FeatureCollection":
        features = geometry.get("features") or []
        if not features:
            raise QuarantineAlert("no_geometry", "GDACS geometry empty")
        geometry = features[0].get("geometry") or {}
        geom_type = geometry.get("type")
    if geom_type == "Point":
        coords = geometry.get("coordinates") or []
        lon, lat = float(coords[0]), float(coords[1])
        geometry_wkt = None
    else:
        geometry_wkt = json.dumps(geometry)
        coords = geometry.get("coordinates", [[[]]])[0][0] if geometry else []
        lon = float(coords[0]) if coords else metadata["lon"]
        lat = float(coords[1]) if len(coords) > 1 else metadata["lat"]
    return ParsedAlert(
        external_id=identifier,
        source_id="gdacs",
        severity=await _gdacs_severity(conn, str(metadata.get("alertlevel", "Green"))),
        headline=str(metadata.get("name") or metadata.get("description") or "GDACS event"),
        body=str(metadata.get("description") or metadata.get("name") or "GDACS event"),
        lang="en",
        lon=lon,
        lat=lat,
        effective_at=effective_at,
        expires_at=expires_at,
        estimated_onset_at=onset,
        raw_checksum=raw.checksum,
        etag=raw.etag,
        geometry_wkt=geometry_wkt,
    )
