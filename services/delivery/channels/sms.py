from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import asyncpg
from twilio.rest import Client

from services.api.settings import settings
from services.delivery.assurance import record
from services.delivery.channels.base import (
    ChannelUnavailable,
    OutboundMessage,
    SendResult,
    StatusUpdate,
)
from services.delivery.webhook_verify import public_webhook_url


class TwilioSmsAdapter:
    code = "sms"
    supports_provider_accept = True
    supports_device_delivered = True
    supports_opened = False
    supports_acknowledgement = True

    def __init__(self, conn: asyncpg.Connection, config: dict[str, Any] | None = None) -> None:
        self._conn = conn
        self._config = config or {}
        self._from = settings.twilio_from_number
        if settings.twilio_account_sid and settings.twilio_auth_token:
            self._client: Client | None = Client(
                settings.twilio_account_sid,
                settings.twilio_auth_token,
            )
        else:
            self._client = None

    async def send(self, msg: OutboundMessage) -> SendResult:
        if self._client is None or not self._from:
            raise ChannelUnavailable("twilio_not_configured")
        from services.api import config_repo

        callback = public_webhook_url("/api/v1/webhooks/sms-status")
        footer = await config_repo.get(self._conn, "response.sms_footer")
        text = f"{msg.headline}\n\n{msg.body}"
        if footer:
            text = f"{text}\n\n{footer}"
        result = await asyncio.to_thread(
            self._client.messages.create,
            to=msg.address,
            from_=self._from,
            body=text,
            status_callback=callback,
        )
        await record(
            self._conn,
            msg.delivery_id,
            "provider_accepted",
            source="twilio_sms_send",
            evidence_id=result.sid,
        )
        return SendResult(provider_ref=result.sid, simulated=False)

    async def parse_webhook(
        self, body: bytes, headers: Mapping[str, str]
    ) -> list[StatusUpdate]:
        return []
