from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx

from services.ingestion.types import NotModified, RawAlert


class GdacsAdapter:
    source_id = "gdacs"
    is_authoritative = True

    def __init__(
        self,
        list_url: str,
        india_bbox: dict[str, float],
        timeout_s: int,
        not_modified_status: int,
    ) -> None:
        self._list_url = list_url
        self._india_bbox = india_bbox
        self._timeout_s = timeout_s
        self._not_modified_status = not_modified_status

    @staticmethod
    def make_identifier(properties: dict[str, Any]) -> str:
        return f"{properties['eventtype']}:{properties['eventid']}:{properties['episodeid']}"

    def _in_india(self, feature: dict[str, Any]) -> bool:
        for country in feature.get("properties", {}).get("affectedcountries", []):
            if country.get("iso3") == "IND":
                return True
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        if len(coords) < 2:
            return False
        lon, lat = float(coords[0]), float(coords[1])
        return (
            self._india_bbox["minlongitude"] <= lon <= self._india_bbox["maxlongitude"]
            and self._india_bbox["minlatitude"] <= lat <= self._india_bbox["maxlatitude"]
        )

    async def discover(self, since: datetime) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(self._list_url)
            response.raise_for_status()
            for feature in response.json().get("features", []):
                props = feature.get("properties") or {}
                modified = props.get("datemodified")
                if modified:
                    modified_dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                    if modified_dt.tzinfo is None:
                        modified_dt = modified_dt.replace(tzinfo=UTC)
                    if modified_dt < since.astimezone(UTC):
                        continue
                if self._in_india(feature):
                    yield self.make_identifier(props)

    async def fetch(self, identifier: str, etag: str | None) -> RawAlert | NotModified:
        eventtype, eventid, episodeid = identifier.split(":")
        geometry_url = (
            "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry"
            f"?eventtype={eventtype}&eventid={eventid}&episodeid={episodeid}"
        )
        headers = {"If-None-Match": etag} if etag else {}
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            list_response = await client.get(self._list_url)
            list_response.raise_for_status()
            feature = None
            for candidate in list_response.json().get("features", []):
                props = candidate.get("properties") or {}
                if self.make_identifier(props) == identifier:
                    feature = candidate
                    break
            if feature is None:
                raise KeyError(identifier)
            geometry_response = await client.get(geometry_url, headers=headers)
        if geometry_response.status_code == self._not_modified_status:
            return NotModified()
        geometry_response.raise_for_status()
        body = geometry_response.content
        return RawAlert(
            body=body,
            etag=geometry_response.headers.get("ETag"),
            fetched_at=datetime.now(UTC),
            checksum=hashlib.sha256(body).hexdigest(),
            content_type=geometry_response.headers.get("content-type", "application/json"),
        )
