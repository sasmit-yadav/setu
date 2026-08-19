from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import asyncpg
import httpx

from services.api import config_repo
from services.api.settings import settings
from services.delivery.channels.base import (
    ChannelUnavailable,
    OutboundMessage,
    SendResult,
    StatusUpdate,
)


class WebhookSirenAdapter:
    code = "siren"
    supports_provider_accept = True
    supports_device_delivered = False
    supports_opened = False
    supports_acknowledgement = False

    def __init__(self, conn: asyncpg.Connection, config: dict[str, Any] | None = None) -> None:
        self._conn = conn
        self._config = config or {}

    async def send(self, msg: OutboundMessage) -> SendResult:
        url = self._config.get("webhook_url") or settings.public_base_url
        if not url:
            raise ChannelUnavailable("siren_webhook_not_configured")
        payload = {"alert_id": msg.alert_id, "delivery_id": msg.delivery_id, "headline": msg.headline}
        error_min = await config_repo.get_int(self._conn, "http.status_client_error_min")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(str(url), json=payload)
        if response.status_code >= error_min:
            raise ChannelUnavailable("siren_webhook_failed")
        return SendResult(provider_ref=f"siren-{msg.delivery_id}", simulated=False)

    async def parse_webhook(
        self, body: bytes, headers: Mapping[str, str]
    ) -> list[StatusUpdate]:
        return []
