from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import asyncpg

from services.api import config_repo
from services.delivery.channels.base import (
    ChannelUnavailable,
    OutboundMessage,
    SendResult,
    StatusUpdate,
)


class PeerRelayAdapter:
    code = "community_relay"
    # Per channel_capability_tier's seed (§8.2): a peer transfer never touches
    # our server, so there is no provider to accept it (False) — but
    # device_delivered and opened ARE provable, just not through this
    # adapter's send()/parse_webhook(). The receiving device verifies the
    # Ed25519 signature client-side and reports both tiers via
    # POST /api/v1/relay/receipt when it reconnects (Rule 11). Declaring
    # these False here would silently disagree with the seeded truth table
    # and fail check_channel_capability.py's whole reason for existing.
    supports_provider_accept = False
    supports_device_delivered = True
    supports_opened = True
    supports_acknowledgement = True

    def __init__(self, conn: asyncpg.Connection, config: dict[str, Any] | None = None) -> None:
        self._conn = conn
        self._config = config or {}

    async def send(self, msg: OutboundMessage) -> SendResult:
        enabled = await config_repo.get_bool(self._conn, "relay.peer_enabled")
        if not enabled:
            raise ChannelUnavailable("peer_relay_disabled")
        raise ChannelUnavailable("peer_relay_client_required")

    async def parse_webhook(
        self, body: bytes, headers: Mapping[str, str]
    ) -> list[StatusUpdate]:
        return []
