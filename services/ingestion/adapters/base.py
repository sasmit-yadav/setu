from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Protocol

from services.ingestion.types import NotModified, RawAlert


class AlertSourceAdapter(Protocol):
    source_id: str
    is_authoritative: bool

    async def discover(self, since: datetime) -> AsyncIterator[str]: ...

    async def fetch(self, identifier: str, etag: str | None) -> RawAlert | NotModified: ...
