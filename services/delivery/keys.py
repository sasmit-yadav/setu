from __future__ import annotations

from services.api.settings import settings


class RedisKeys:
    def __init__(self, namespace: str | None = None) -> None:
        self._ns = namespace or settings.redis_namespace

    def stream_delivery(self) -> str:
        return f"{self._ns}:stream:delivery"

    def group(self) -> str:
        return f"{self._ns}:group:workers"

    def zset_retry(self) -> str:
        return f"{self._ns}:zset:retry"

    def zset_assistance(self) -> str:
        return f"{self._ns}:zset:assistance"

    def channel_alert(self, alert_id: int) -> str:
        return f"{self._ns}:chan:alert:{alert_id}"

    def channel_ops(self) -> str:
        return f"{self._ns}:chan:ops"

    def lock_ingest(self, source_id: str) -> str:
        return f"{self._ns}:lock:ingest:{source_id}"

    def lock_supersede(self, incident_id: int) -> str:
        return f"{self._ns}:lock:supersede:{incident_id}"

    def receipt_nonce(self, delivery_id: int) -> str:
        return f"{self._ns}:receipt:nonce:{delivery_id}"


keys = RedisKeys()
