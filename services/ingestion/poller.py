from __future__ import annotations

from datetime import UTC, datetime, timedelta

import asyncpg
import httpx

from services.ingestion.adapters.gdacs import GdacsAdapter
from services.ingestion.adapters.thunderstorm import ThunderstormNowcastAdapter
from services.ingestion.adapters.usgs import UsgsAdapter
from services.ingestion.normalize import parse_gdacs, parse_thunderstorm, parse_usgs
from services.ingestion.persist import upsert_alert
from services.ingestion.registry import load_adapters
from services.ingestion.types import NotModified, QuarantineAlert


async def _quarantine(conn: asyncpg.Connection, source_id: str, raw_body: bytes, reason: str, detail: str) -> None:
    await conn.execute(
        """
        INSERT INTO alert_quarantine (source_id, raw, reason, detail)
        VALUES ($1, $2, $3, $4)
        """,
        source_id,
        raw_body,
        reason,
        detail,
    )


async def poll_source(conn: asyncpg.Connection, source_id: str, since: datetime | None = None) -> list[int]:
    adapters = await load_adapters(conn)
    adapter = adapters.get(source_id)
    if adapter is None:
        raise KeyError(source_id)
    if since is None:
        hours = await conn.fetchval(
            "SELECT value::int FROM app_config WHERE key = 'ingest.poll_lookback_hours'"
        )
        since = datetime.now(UTC) - timedelta(hours=int(hours))
    alert_ids: list[int] = []
    async for identifier in adapter.discover(since):
        existing_etag = await conn.fetchval(
            "SELECT etag FROM alert WHERE source_id = $1 AND external_id = $2",
            source_id,
            identifier,
        )
        try:
            if isinstance(adapter, UsgsAdapter):
                raw = await adapter.fetch_feature_from_collection(identifier, since)
            else:
                fetched = await adapter.fetch(identifier, existing_etag)
                if isinstance(fetched, NotModified):
                    continue
                raw = fetched
            if isinstance(adapter, UsgsAdapter):
                parsed = await parse_usgs(conn, raw)
            elif isinstance(adapter, GdacsAdapter):
                metadata = await _gdacs_metadata(adapter, identifier)
                parsed = await parse_gdacs(conn, identifier, raw, metadata)
            elif isinstance(adapter, ThunderstormNowcastAdapter):
                parsed = await parse_thunderstorm(conn, raw)
            else:
                continue
            alert_id = await upsert_alert(conn, parsed)
            alert_ids.append(alert_id)
        except (KeyError, httpx.HTTPError, ValueError, QuarantineAlert) as exc:
            if isinstance(exc, QuarantineAlert):
                body = raw.body if "raw" in locals() else b""
                await _quarantine(conn, source_id, body, exc.reason, exc.detail)
            else:
                await _quarantine(conn, source_id, b"", "ingest_error", str(exc))
    return alert_ids


async def _gdacs_metadata(adapter: GdacsAdapter, identifier: str) -> dict:
    async with httpx.AsyncClient(timeout=adapter._timeout_s) as client:
        response = await client.get(adapter._list_url)
        response.raise_for_status()
        for feature in response.json().get("features", []):
            props = feature.get("properties") or {}
            if adapter.make_identifier(props) == identifier:
                geometry = feature.get("geometry") or {}
                coords = geometry.get("coordinates") or [0, 0]
                return {
                    **props,
                    "lon": float(coords[0]),
                    "lat": float(coords[1]),
                }
    raise KeyError(identifier)
