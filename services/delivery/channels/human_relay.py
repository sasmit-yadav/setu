from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import asyncpg

from services.delivery.channels.base import (
    ChannelUnavailable,
    OutboundMessage,
    SendResult,
    StatusUpdate,
)


class HumanRelayAdapter:
    code = "human_relay"
    supports_provider_accept = True
    supports_device_delivered = True
    supports_opened = False
    supports_acknowledgement = True

    def __init__(self, conn: asyncpg.Connection, config: dict[str, Any] | None = None) -> None:
        self._conn = conn
        self._config = config or {}

    async def send(self, msg: OutboundMessage) -> SendResult:
        raise ChannelUnavailable("human_relay_requires_ivr_path")

    async def parse_webhook(
        self, body: bytes, headers: Mapping[str, str]
    ) -> list[StatusUpdate]:
        return []
