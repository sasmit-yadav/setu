from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx

from services.ingestion.types import NotModified, RawAlert


class UsgsAdapter:
    source_id = "usgs"
    is_authoritative = True

    def __init__(
        self,
        feed_url: str,
        bbox: dict[str, float],
        timeout_s: int,
        not_modified_status: int,
        min_magnitude: float | None = None,
    ) -> None:
        self._feed_url = feed_url
        self._bbox = bbox
        self._timeout_s = timeout_s
        self._not_modified_status = not_modified_status
        # Optional because the India bbox is small enough to ingest unfiltered.
        # Widen the bbox toward global and it stops being optional in practice:
        # USGS lists every micro-quake it records, so a worldwide poll without
        # this returns hundreds of M1s a day and buries the officer's inbox.
        # Left None when absent so the existing seeded config is unchanged.
        self._min_magnitude = min_magnitude

    def _params(self, since: datetime) -> dict[str, Any]:
        params: dict[str, Any] = {
            "format": "geojson",
            "starttime": since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
            "minlatitude": self._bbox["minlatitude"],
            "maxlatitude": self._bbox["maxlatitude"],
            "minlongitude": self._bbox["minlongitude"],
            "maxlongitude": self._bbox["maxlongitude"],
        }
        if self._min_magnitude is not None:
            params["minmagnitude"] = self._min_magnitude
        return params

    async def discover(self, since: datetime) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(self._feed_url, params=self._params(since))
            response.raise_for_status()
            for feature in response.json().get("features", []):
                feature_id = feature.get("id")
                if feature_id:
                    yield str(feature_id)

    async def fetch(self, identifier: str, etag: str | None) -> RawAlert | NotModified:
        headers = {"If-None-Match": etag} if etag else {}
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(
                self._feed_url,
                params={"format": "geojson", "eventid": identifier},
                headers=headers,
            )
        if response.status_code == self._not_modified_status:
            return NotModified()
        response.raise_for_status()
        body = response.content
        return RawAlert(
            body=body,
            etag=response.headers.get("ETag"),
            fetched_at=datetime.now(UTC),
            checksum=hashlib.sha256(body).hexdigest(),
        )

    async def fetch_feature_from_collection(self, identifier: str, since: datetime) -> RawAlert:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(self._feed_url, params=self._params(since))
            response.raise_for_status()
            payload = response.json()
        for feature in payload.get("features", []):
            if str(feature.get("id")) == identifier:
                body = json.dumps(feature, sort_keys=True).encode()
                return RawAlert(
                    body=body,
                    etag=None,
                    fetched_at=datetime.now(UTC),
                    checksum=hashlib.sha256(body).hexdigest(),
                )
        raise KeyError(identifier)
