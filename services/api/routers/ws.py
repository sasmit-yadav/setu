from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from services.api.auth import AuthError, decode_access_token
from services.api.deps import close_redis
from services.api.rbac import OPERATIONAL_READ_ROLES
from services.api.settings import settings
from services.delivery.keys import keys

router = APIRouter()


@router.websocket("/api/v1/ws/ops")
async def ops_socket(websocket: WebSocket, token: str | None = None) -> None:
    await websocket.accept()
    if not token:
        await websocket.close(code=4401)
        return
    try:
        principal = decode_access_token(token)
    except AuthError:
        await websocket.close(code=4401)
        return
    if principal.role not in OPERATIONAL_READ_ROLES:
        await websocket.close(code=4403)
        return
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(keys.channel_ops())
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("data"):
                raw = message["data"]
                await websocket.send_text(raw if isinstance(raw, str) else json.dumps(raw))
            else:
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                except TimeoutError:
                    pass
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        await pubsub.unsubscribe(keys.channel_ops())
        closer = getattr(pubsub, "aclose", None)
        if closer is not None:
            await closer()
        else:
            await pubsub.close()
        await close_redis(redis)
