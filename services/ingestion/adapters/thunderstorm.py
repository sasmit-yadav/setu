from __future__ import annotations

import asyncio
import hashlib
import json
import math
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx

from services.ingestion.types import NotModified, RawAlert


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


class ThunderstormNowcastAdapter:
    source_id = "thunderstorm_nowcast"
    is_authoritative = False

    def __init__(
        self,
        base_url: str,
        timeout_s: int,
        not_modified_status: int,
        conn: Any | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout_s = timeout_s
        self._not_modified_status = not_modified_status
        self._conn = conn
        self._pending: dict[str, dict[str, Any]] = {}

    def _identifier(self, unit_id: int, hour: str) -> str:
        return f"{unit_id}:{hour}"

    async def discover(self, since: datetime) -> AsyncIterator[str]:
        if self._conn is None:
            return
        from services.api import config_repo

        cape_floor = await config_repo.get_float(self._conn, "thunderstorm.cape_floor")
        cape_scale = await config_repo.get_float(self._conn, "thunderstorm.cape_scale")
        li_ceiling = await config_repo.get_float(self._conn, "thunderstorm.li_ceiling")
        li_scale = await config_repo.get_float(self._conn, "thunderstorm.li_scale")
        alert_floor = await config_repo.get_float(self._conn, "thunderstorm.alert_floor")
        precip_scale = await config_repo.get_float(
            self._conn, "thunderstorm.precip_probability_scale"
        )
        geometry_level = await config_repo.get_int(self._conn, "thunderstorm.geometry_level")
        max_units = await config_repo.get_int(self._conn, "thunderstorm.max_units_per_poll")
        concurrent = await config_repo.get_int(self._conn, "thunderstorm.max_concurrent_fetches")
        forecast_days = await config_repo.get_int(self._conn, "thunderstorm.forecast_days")
        bbox_min_lon = await config_repo.get_float(self._conn, "map.india_min_lon")
        bbox_min_lat = await config_repo.get_float(self._conn, "map.india_min_lat")
        bbox_max_lon = await config_repo.get_float(self._conn, "map.india_max_lon")
        bbox_max_lat = await config_repo.get_float(self._conn, "map.india_max_lat")

        units = await self._conn.fetch(
            """
            SELECT id, name,
                   ST_X(ST_Centroid(geom::geometry)) AS lon,
                   ST_Y(ST_Centroid(geom::geometry)) AS lat
            FROM admin_unit
            WHERE level = $1
              AND ST_Intersects(
                    geom,
                    ST_MakeEnvelope($2, $3, $4, $5, 4326)
                  )
            ORDER BY ST_Area(geom::geometry) DESC
            LIMIT $6
            """,
            geometry_level,
            bbox_min_lon,
            bbox_min_lat,
            bbox_max_lon,
            bbox_max_lat,
            max_units,
        )
        semaphore = asyncio.Semaphore(concurrent)
        since_utc = since.astimezone(UTC)

        async def score_unit(row: Any) -> list[tuple[str, dict[str, Any]]]:
            async with semaphore:
                params = {
                    "latitude": float(row["lat"]),
                    "longitude": float(row["lon"]),
                    "hourly": "cape,lifted_index,convective_inhibition,precipitation_probability",
                    "forecast_days": forecast_days,
                    "timezone": "UTC",
                }
                async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                    response = await client.get(self._base_url, params=params)
                    response.raise_for_status()
                    payload = response.json()
            hourly = payload.get("hourly") or {}
            times = hourly.get("time") or []
            capes = hourly.get("cape") or []
            lifted = hourly.get("lifted_index") or []
            cins = hourly.get("convective_inhibition") or []
            precips = hourly.get("precipitation_probability") or []
            hits: list[tuple[str, dict[str, Any]]] = []
            for index, stamp in enumerate(times):
                hour_at = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                if hour_at.tzinfo is None:
                    hour_at = hour_at.replace(tzinfo=UTC)
                if hour_at < since_utc:
                    continue
                cape = capes[index] if index < len(capes) else None
                li = lifted[index] if index < len(lifted) else None
                precip = precips[index] if index < len(precips) else None
                if cape is None or li is None or precip is None:
                    continue
                precip_unit = float(precip) / precip_scale
                risk = (
                    sigmoid((float(cape) - cape_floor) / cape_scale)
                    * sigmoid((li_ceiling - float(li)) / li_scale)
                    * precip_unit
                )
                if risk < alert_floor:
                    continue
                ident = self._identifier(int(row["id"]), hour_at.isoformat())
                hits.append(
                    (
                        ident,
                        {
                            "unit_id": int(row["id"]),
                            "unit_name": row["name"],
                            "lon": float(row["lon"]),
                            "lat": float(row["lat"]),
                            "hour": hour_at.isoformat(),
                            "cape": float(cape),
                            "lifted_index": float(li),
                            "cin": float(cins[index]) if index < len(cins) and cins[index] is not None else None,
                            "precipitation_probability": float(precip),
                            "risk": risk,
                        },
                    )
                )
            return hits

        batches = await asyncio.gather(*(score_unit(row) for row in units))
        for hits in batches:
            for ident, payload in hits:
                self._pending[ident] = payload
                yield ident

    async def fetch(self, identifier: str, etag: str | None) -> RawAlert | NotModified:
        payload = self._pending.get(identifier)
        if payload is None:
            raise KeyError(identifier)
        body = json.dumps(payload, sort_keys=True).encode()
        checksum = hashlib.sha256(body).hexdigest()
        if etag and etag == checksum:
            return NotModified()
        return RawAlert(
            body=body,
            etag=checksum,
            fetched_at=datetime.now(UTC),
            checksum=checksum,
            content_type="application/json",
        )
