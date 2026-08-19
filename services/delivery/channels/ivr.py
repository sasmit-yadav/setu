from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode

import asyncpg
from twilio.rest import Client

from services.api import config_repo
from services.api.settings import settings
from services.delivery.assurance import record
from services.delivery.channels.base import (
    ChannelUnavailable,
    OutboundMessage,
    SendResult,
    StatusUpdate,
)
from services.delivery.webhook_verify import public_webhook_url


class TwilioIvrAdapter:
    code = "ivr"
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

    async def _twiml_url(self, delivery_id: int) -> str:
        gather_digits = await config_repo.get_str(self._conn, "ivr.gather_digits")
        gather_timeout = await config_repo.get_str(self._conn, "ivr.gather_timeout_s")
        action = public_webhook_url("/api/v1/webhooks/ivr-status")
        params = urlencode(
            {
                "delivery_id": delivery_id,
                "gather_digits": gather_digits,
                "gather_timeout": gather_timeout,
                "action": action,
            }
        )
        return public_webhook_url(f"/api/v1/webhooks/ivr-twiml?{params}")

    async def send(self, msg: OutboundMessage) -> SendResult:
        if self._client is None or not self._from:
            raise ChannelUnavailable("twilio_not_configured")
        callback = public_webhook_url("/api/v1/webhooks/ivr-status")
        twiml_url = await self._twiml_url(msg.delivery_id)
        result = await asyncio.to_thread(
            self._client.calls.create,
            to=msg.address,
            from_=self._from,
            url=twiml_url,
            status_callback=callback,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
        )
        await record(
            self._conn,
            msg.delivery_id,
            "provider_accepted",
            source="twilio_ivr_send",
            evidence_id=result.sid,
        )
        return SendResult(provider_ref=result.sid, simulated=False)

    async def parse_webhook(
        self, body: bytes, headers: Mapping[str, str]
    ) -> list[StatusUpdate]:
        return []
