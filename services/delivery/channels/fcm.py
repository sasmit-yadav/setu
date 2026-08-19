from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from typing import Any

import asyncpg
import firebase_admin
from firebase_admin import credentials, messaging

from services.api.settings import settings
from services.delivery.assurance import record
from services.delivery.channels.base import (
    ChannelUnavailable,
    OutboundMessage,
    SendResult,
    StatusUpdate,
)

_app_initialized = False


def _ensure_firebase() -> None:
    global _app_initialized
    if _app_initialized:
        return
    path = settings.fcm_service_account_json
    if not path or not os.path.isfile(path):
        raise ChannelUnavailable("fcm_not_configured")
    cred = credentials.Certificate(path)
    firebase_admin.initialize_app(cred)
    _app_initialized = True


class FcmAdapter:
    code = "fcm"
    supports_provider_accept = True
    supports_device_delivered = True
    supports_opened = True
    supports_acknowledgement = True

    def __init__(self, conn: asyncpg.Connection, config: dict[str, Any] | None = None) -> None:
        self._conn = conn
        self._config = config or {}

    async def send(self, msg: OutboundMessage) -> SendResult:
        _ensure_firebase()
        data = {
            "alert_id": str(msg.alert_id),
            "delivery_id": str(msg.delivery_id),
            "ack_url": msg.ack_url,
        }
        if msg.receipt_nonce:
            data["receipt_nonce"] = msg.receipt_nonce
        if msg.signature:
            data["signature"] = msg.signature
        message = messaging.Message(
            notification=messaging.Notification(title=msg.headline, body=msg.body),
            data=data,
            token=msg.address,
        )
        provider_ref = await asyncio.to_thread(messaging.send, message)
        await record(
            self._conn,
            msg.delivery_id,
            "provider_accepted",
            source="fcm_send",
            evidence_id=provider_ref,
        )
        return SendResult(provider_ref=provider_ref, simulated=False)

    async def parse_webhook(
        self, body: bytes, headers: Mapping[str, str]
    ) -> list[StatusUpdate]:
        return []
