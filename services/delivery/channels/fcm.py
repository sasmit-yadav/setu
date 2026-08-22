from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from typing import Any

import asyncpg

from services.api.settings import settings
from services.delivery.assurance import record
from services.delivery.channels.base import (
    ChannelUnavailable,
    OutboundMessage,
    SendResult,
    StatusUpdate,
)

_app_initialized = False
_messaging: Any = None


def _load_firebase():
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
    except ImportError as exc:
        raise ChannelUnavailable("fcm_not_configured") from exc
    return firebase_admin, credentials, messaging


def _ensure_firebase() -> Any:
    global _app_initialized, _messaging
    if _app_initialized and _messaging is not None:
        return _messaging
    firebase_admin, credentials, messaging = _load_firebase()
    path = settings.fcm_service_account_json
    if not path or not os.path.isfile(path):
        raise ChannelUnavailable("fcm_not_configured")
    cred = credentials.Certificate(path)
    firebase_admin.initialize_app(cred)
    _app_initialized = True
    _messaging = messaging
    return messaging


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
        messaging = _ensure_firebase()
        data = {
            "alert_id": str(msg.alert_id),
            "delivery_id": str(msg.delivery_id),
            "ack_url": msg.ack_url,
            "headline": msg.headline,
            "body": msg.body,
        }
        if msg.receipt_nonce:
            data["receipt_nonce"] = msg.receipt_nonce
        if msg.signature:
            data["signature"] = msg.signature
        # Data-only webpush: a `notification` block is delivered straight to the
        # browser's own notification tray, bypassing our service worker's `push`
        # handler entirely — which is where the receipt_nonce round-trip lives
        # (sw.ts). Web push must stay data-only or device_delivered never fires.
        message = messaging.Message(
            data=data,
            token=msg.address,
            webpush=messaging.WebpushConfig(headers={"Urgency": "high"}),
        )
        try:
            provider_ref = await asyncio.to_thread(messaging.send, message)
        except Exception as exc:
            # Stale PWA token (UnregisteredError) must not crash the worker.
            # It is a dead address, not a retryable carrier blip.
            if type(exc).__name__ in {"UnregisteredError", "SenderIdMismatchError"}:
                raise ChannelUnavailable("device_unregistered") from exc
            raise
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
