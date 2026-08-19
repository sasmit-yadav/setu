from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from services.api import config_repo
from services.api.deps import get_conn
from services.crypto.alert_signing import public_key_b64

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/signing-key")
async def signing_key() -> dict[str, str]:
    try:
        return {"public_key_b64": public_key_b64()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="signing_not_configured") from exc


@router.get("/config")
async def public_config(conn: asyncpg.Connection = Depends(get_conn)) -> dict[str, str | int]:
    keys = [
        "pwa.network_timeout_seconds",
        "pwa.alert_cache_max_age_seconds",
        "pwa.ack_retention_minutes",
        "pwa.receipt_retention_minutes",
        "response.free_text_max_chars",
    ]
    out: dict[str, str | int] = {}
    for key in keys:
        value = await config_repo.get(conn, key)
        if value is not None:
            try:
                out[key] = int(value)
            except ValueError:
                try:
                    out[key] = float(value)
                except ValueError:
                    out[key] = value
    return out
