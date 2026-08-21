from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from services.delivery.keys import keys


async def publish_ops(redis: Redis, event: dict[str, Any]) -> None:
    await redis.publish(keys.channel_ops(), json.dumps(event))
    alert_id = event.get("alert_id")
    if alert_id is not None:
        await redis.publish(keys.channel_alert(int(alert_id)), json.dumps(event))
