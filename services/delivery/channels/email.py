from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import asyncpg
import httpx

from services.api import config_repo
from services.api.settings import settings
from services.delivery.assurance import record
from services.delivery.channels.base import (
    ChannelUnavailable,
    OutboundMessage,
    SendResult,
    StatusUpdate,
)


class BrevoAdapter:
    code = "email"
    supports_provider_accept = True
    supports_device_delivered = False
    supports_opened = False
    supports_acknowledgement = True

    def __init__(self, conn: asyncpg.Connection, config: dict[str, Any] | None = None) -> None:
        self._conn = conn
        self._config = config or {}

    async def send(self, msg: OutboundMessage) -> SendResult:
        if not settings.brevo_api_key:
            raise ChannelUnavailable("brevo_not_configured")
        error_min = await config_repo.get_int(self._conn, "http.status_client_error_min")
        payload = {
            "sender": {"email": self._config.get("from_email", "alerts@setu.local")},
            "to": [{"email": msg.address}],
            "subject": msg.headline,
            "textContent": msg.body,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": settings.brevo_api_key,
                    "content-type": "application/json",
                },
                json=payload,
            )
        if response.status_code >= error_min:
            raise ChannelUnavailable("brevo_send_failed")
        provider_ref = response.headers.get("x-message-id") or response.json().get("messageId", "")
        await record(
            self._conn,
            msg.delivery_id,
            "provider_accepted",
            source="brevo_send",
            evidence_id=str(provider_ref),
        )
        return SendResult(provider_ref=str(provider_ref), simulated=False)

    async def parse_webhook(
        self, body: bytes, headers: Mapping[str, str]
    ) -> list[StatusUpdate]:
        return []
