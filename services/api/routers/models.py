from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends

from services.api.auth import Principal
from services.api.deps import get_conn
from services.api.rbac import require_models_read

router = APIRouter(prefix="/api/v1", tags=["models"])


@router.get("/models")
async def list_models(
    conn: asyncpg.Connection = Depends(get_conn),
    _principal: Principal = Depends(require_models_read),
) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT name, version, is_bootstrap, metrics, artifact_uri, active
        FROM model_registry
        ORDER BY name, version
        """
    )
    return [dict(row) for row in rows]
