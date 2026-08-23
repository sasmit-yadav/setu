from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class OutboundMessage:
    alert_id: int
    delivery_id: int
    recipient_id: int
    channel_code: str
    address: str
    headline: str
    body: str
    ack_url: str
    # The language headline/body were actually resolved into, so a channel can
    # localise the text IT adds (the SMS reply-instruction footer) instead of
    # stapling English onto a Malayalam warning.
    lang: str | None = None
    receipt_nonce: str | None = None
    signature: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SendResult:
    provider_ref: str
    simulated: bool


@dataclass(frozen=True)
class StatusUpdate:
    delivery_id: int
    event_type: str
    evidence_id: str | None
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ChannelUnavailable(Exception):
    def __init__(self, code: str, remediation: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.remediation = remediation


class TransientChannelError(Exception):
    pass


class ChannelAdapter(Protocol):
    code: str
    supports_provider_accept: bool
    supports_device_delivered: bool
    supports_opened: bool
    supports_acknowledgement: bool

    async def send(self, msg: OutboundMessage) -> SendResult: ...

    async def parse_webhook(
        self, body: bytes, headers: Mapping[str, str]
    ) -> list[StatusUpdate]: ...
