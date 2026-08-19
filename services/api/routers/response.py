from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from services.api import config_repo
from services.api.deps import get_conn, get_idempotency_key
from services.api.schemas import CitizenResponseOut, CitizenResponseRequest
from services.response.citizen_response import ResponseError, submit_response

router = APIRouter(prefix="/api/v1", tags=["citizen"])


@router.post("/response", response_model=CitizenResponseOut)
async def post_response(
    body: CitizenResponseRequest,
    conn: asyncpg.Connection = Depends(get_conn),
    idempotency_key: str | None = Depends(get_idempotency_key),
) -> CitizenResponseOut:
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header required")
    if body.free_text is not None:
        max_chars = await config_repo.get_int(conn, "response.free_text_max_chars")
        if len(body.free_text) > max_chars:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "free_text_too_long",
                    "message": f"free_text exceeds {max_chars} characters",
                },
            )
    location = None
    if body.lat is not None and body.lon is not None:
        location = (body.lon, body.lat)
    try:
        result = await submit_response(
            conn,
            delivery_id=body.delivery_id,
            response_type=body.response_type,
            idempotency_key=idempotency_key,
            free_text=body.free_text,
            location=location,
            location_consent=body.location_consent,
            submitted_at=body.submitted_at,
        )
    except ResponseError as exc:
        raise HTTPException(status_code=422, detail={"error": exc.code, "message": exc.message}) from exc
    return CitizenResponseOut(**result)
