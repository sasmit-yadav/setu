from __future__ import annotations

import asyncio
import random
import uuid
from collections.abc import Mapping
from typing import Any

import asyncpg

from services.api import config_repo
from services.delivery.assurance import record
from services.delivery.channels.base import (
    OutboundMessage,
    SendResult,
    StatusUpdate,
    TransientChannelError,
)


class SimulatedCarrierAdapter:
    code = "sim"
    supports_provider_accept = True
    supports_device_delivered = True
    supports_opened = True
    supports_acknowledgement = True

    def __init__(self, conn: asyncpg.Connection, channel_config: dict[str, Any] | None = None) -> None:
        self._conn = conn
        self._channel_config = channel_config or {}

    async def _profile(self, channel_code: str) -> dict[str, float]:
        profiles = self._channel_config.get("profiles", {})
        profile = profiles.get(channel_code, profiles.get("default", {}))
        latency_min = profile.get("latency_ms_min")
        latency_max = profile.get("latency_ms_max")
        failure_rate = profile.get("failure_rate")
        if latency_min is None:
            latency_min = float(await config_repo.get(self._conn, "simulated.latency_ms_min"))
        if latency_max is None:
            latency_max = float(await config_repo.get(self._conn, "simulated.latency_ms_max"))
        if failure_rate is None:
            failure_rate = float(await config_repo.get(self._conn, "simulated.failure_rate"))
        ms_to_seconds = float(await config_repo.get(self._conn, "simulated.ms_to_seconds"))
        return {
            "latency_ms_min": float(latency_min),
            "latency_ms_max": float(latency_max),
            "failure_rate": float(failure_rate),
            "ms_to_seconds": ms_to_seconds,
        }

    async def send(self, msg: OutboundMessage) -> SendResult:
        profile = await self._profile(msg.channel_code)
        delay_s = random.uniform(
            profile["latency_ms_min"],
            profile["latency_ms_max"],
        ) * profile["ms_to_seconds"]
        await asyncio.sleep(delay_s)
        if random.random() < profile["failure_rate"]:
            raise TransientChannelError("simulated_carrier_failure")
        provider_ref = f"sim-{uuid.uuid4()}"
        await record(
            self._conn,
            msg.delivery_id,
            "provider_accepted",
            source="simulated_carrier_profile",
            evidence_id=provider_ref,
        )
        return SendResult(provider_ref=provider_ref, simulated=True)

    async def parse_webhook(
        self, body: bytes, headers: Mapping[str, str]
    ) -> list[StatusUpdate]:
        return []
