from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RawAlert:
    body: bytes
    etag: str | None
    fetched_at: datetime
    checksum: str
    content_type: str = "application/json"


@dataclass(frozen=True)
class NotModified:
    pass


@dataclass(frozen=True)
class ParsedAlert:
    external_id: str
    source_id: str
    severity: str
    headline: str
    body: str
    lang: str
    lon: float
    lat: float
    effective_at: datetime
    expires_at: datetime
    estimated_onset_at: datetime | None
    raw_checksum: str
    etag: str | None
    geometry_wkt: str | None = None
    cluster_id: int | None = None


class QuarantineAlert(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail
