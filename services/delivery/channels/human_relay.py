from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode

import asyncpg

from services.api import config_repo
from services.api.settings import settings
from services.audit.ledger import append_audit
from services.delivery.assurance import record
from services.delivery.channels.base import (
    ChannelUnavailable,
    OutboundMessage,
    SendResult,
    StatusUpdate,
)
from services.delivery.webhook_verify import public_webhook_url


async def find_relay_node(conn: asyncpg.Connection, unit_id: int) -> asyncpg.Record | None:
    kinds = await config_repo.get_csv(conn, "relay.node_kind_priority")
    return await conn.fetchrow(
        """
        WITH RECURSIVE chain AS (
            SELECT id, parent_id, 0 AS depth FROM admin_unit WHERE id = $1
            UNION ALL
            SELECT u.id, u.parent_id, chain.depth + 1
            FROM admin_unit u
            JOIN chain ON u.id = chain.parent_id
        )
        SELECT rn.id, rn.unit_id, rn.kind, rn.name, rn.phone_enc
        FROM relay_node rn
        JOIN chain c ON c.id = rn.unit_id
        WHERE rn.active
        ORDER BY array_position($2::text[], rn.kind), c.depth
        LIMIT 1
        """,
        unit_id,
        kinds,
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
        self._from = settings.twilio_from_number
        self._client = None
        if settings.twilio_account_sid and settings.twilio_auth_token:
            try:
                from twilio.rest import Client
            except ImportError:
                self._client = None
            else:
                self._client = Client(
                    settings.twilio_account_sid,
                    settings.twilio_auth_token,
                )

    async def _unit_id(self, recipient_id: int) -> int | None:
        return await self._conn.fetchval(
            "SELECT unit_id FROM recipient WHERE id = $1",
            recipient_id,
        )

    async def _relay_node(self, unit_id: int) -> asyncpg.Record | None:
        return await find_relay_node(self._conn, unit_id)

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
                "mode": "relay",
            }
        )
        return public_webhook_url(f"/api/v1/webhooks/ivr-twiml?{params}")

    async def send(self, msg: OutboundMessage) -> SendResult:
        unit_id = await self._unit_id(msg.recipient_id)
        if unit_id is None:
            raise ChannelUnavailable("recipient_no_unit")
        node = await self._relay_node(unit_id)
        if node is None:
            incident_id = await self._conn.fetchval(
                "SELECT incident_id FROM alert WHERE id = $1",
                msg.alert_id,
            )
            await append_audit(
                self._conn,
                alert_id=msg.alert_id,
                incident_id=incident_id,
                delivery_id=msg.delivery_id,
                event_type="relay.unavailable",
                payload={"unit_id": unit_id, "reason": "no_relay_node_registered_for_unit"},
                actor="human_relay",
            )
            raise ChannelUnavailable("no_relay_node_registered_for_unit")
        if self._client is None or not self._from:
            raise ChannelUnavailable("twilio_not_configured")
        if not settings.pgcrypto_sym_key or not node["phone_enc"]:
            raise ChannelUnavailable("relay_phone_unavailable")
        phone = await self._conn.fetchval(
            "SELECT pgp_sym_decrypt($1, $2)",
            node["phone_enc"],
            settings.pgcrypto_sym_key,
        )
        if not phone:
            raise ChannelUnavailable("relay_phone_unavailable")
        address = phone.decode() if isinstance(phone, bytes) else str(phone)
        callback = public_webhook_url("/api/v1/webhooks/ivr-status")
        twiml_url = await self._twiml_url(msg.delivery_id)
        result = await asyncio.to_thread(
            self._client.calls.create,
            to=address,
            from_=self._from,
            url=twiml_url,
            status_callback=callback,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
        )
        await record(
            self._conn,
            msg.delivery_id,
            "provider_accepted",
            source="twilio_relay_send",
            evidence_id=result.sid,
        )
        return SendResult(provider_ref=result.sid, simulated=False)

    async def parse_webhook(
        self, body: bytes, headers: Mapping[str, str]
    ) -> list[StatusUpdate]:
        return []


async def confirm_relay_delivery(
    conn: asyncpg.Connection,
    delivery_id: int,
    *,
    method: str,
    actor: str,
    digits: str | None = None,
) -> bool:
    if digits is not None:
        expected = await config_repo.get_str(conn, "relay.dtmf.confirm")
        if digits != expected:
            return False
    channel = await conn.fetchval(
        """
        SELECT c.code FROM delivery d
        JOIN channel c ON c.id = d.channel_id
        WHERE d.id = $1
        """,
        delivery_id,
    )
    if channel != "human_relay":
        return False
    recipient_unit = await conn.fetchval(
        """
        SELECT r.unit_id FROM delivery d
        JOIN recipient r ON r.id = d.recipient_id
        WHERE d.id = $1
        """,
        delivery_id,
    )
    if recipient_unit is None:
        return False
    adapter = HumanRelayAdapter(conn)
    node = await adapter._relay_node(int(recipient_unit))
    if node is None:
        return False
    inserted = await conn.fetchval(
        """
        INSERT INTO relay_confirmation (
            delivery_id, relay_node_id, unit_id, confirmed_by_human, method
        )
        VALUES ($1, $2, $3, true, $4)
        ON CONFLICT (delivery_id, relay_node_id) DO NOTHING
        RETURNING id
        """,
        delivery_id,
        node["id"],
        node["unit_id"],
        method,
    )
    if inserted is None:
        return False
    alert = await conn.fetchrow(
        "SELECT alert_id FROM delivery WHERE id = $1",
        delivery_id,
    )
    incident_id = None
    if alert:
        incident_id = await conn.fetchval(
            "SELECT incident_id FROM alert WHERE id = $1",
            alert["alert_id"],
        )
    await append_audit(
        conn,
        alert_id=alert["alert_id"] if alert else None,
        incident_id=incident_id,
        delivery_id=delivery_id,
        event_type="relay.confirmed",
        payload={"relay_node_id": node["id"], "method": method},
        actor=actor,
    )
    await record(
        conn,
        delivery_id,
        "acknowledged",
        source=method,
        evidence_id=str(inserted),
    )
    return True


async def confirm_relay_from_dtmf(
    conn: asyncpg.Connection,
    delivery_id: int,
    digits: str,
) -> bool:
    return await confirm_relay_delivery(
        conn,
        delivery_id,
        method="ivr_dtmf",
        actor="relay_node",
        digits=digits,
    )
