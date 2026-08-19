from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis

from services.api.deps import get_conn, get_redis
from services.api.schemas import ReceiptRequest, ReceiptResponse
from services.delivery.receipts import consume_nonce, record_receipt

router = APIRouter(prefix="/api/v1/deliveries", tags=["receipts"])


@router.post("/{delivery_id}/receipt", response_model=ReceiptResponse)
async def delivery_receipt(
    delivery_id: int,
    body: ReceiptRequest,
    conn: asyncpg.Connection = Depends(get_conn),
    redis: Redis = Depends(get_redis),
) -> ReceiptResponse:
    exists = await conn.fetchval("SELECT 1 FROM delivery WHERE id = $1", delivery_id)
    if not exists:
        raise HTTPException(status_code=404, detail="delivery_not_found")
    if not await consume_nonce(redis, delivery_id, body.receipt_nonce):
        raise HTTPException(status_code=403, detail={"code": "invalid_receipt_nonce"})
    try:
        inserted = await record_receipt(
            conn,
            delivery_id,
            event_type=body.event_type,
            nonce=body.receipt_nonce,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)}) from exc
    return ReceiptResponse(delivery_id=delivery_id, recorded=inserted)
