from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends

from services.api.deps import get_conn

router = APIRouter(prefix="/api/v1", tags=["methodology"])


@router.get("/methodology")
async def methodology(conn: asyncpg.Connection = Depends(get_conn)) -> dict:
    config_rows = await conn.fetch(
        "SELECT key, value, unit, note FROM app_config ORDER BY key"
    )
    capability = await conn.fetch(
        """
        SELECT c.code AS channel_code, t.tier, t.supported,
               t.device_delivered_source AS evidence_source,
               t.not_applicable_reason
        FROM channel_capability_tier t
        JOIN channel c ON c.id = t.channel_id
        ORDER BY c.code, t.tier
        """
    )
    sources = await conn.fetch(
        """
        SELECT source_id, is_authoritative, enabled, poll_interval_s
        FROM alert_source
        ORDER BY source_id
        """
    )
    models = await conn.fetch(
        """
        SELECT name, version, is_bootstrap, metrics, artifact_uri, active
        FROM model_registry
        ORDER BY name, version
        """
    )
    limitation_rows = await conn.fetch(
        """
        SELECT value FROM app_config
        WHERE key LIKE 'methodology.limitation.%'
        ORDER BY key
        """
    )
    return {
        "app_config": [dict(row) for row in config_rows],
        "channel_capability": [dict(row) for row in capability],
        "alert_sources": [dict(row) for row in sources],
        "models": [dict(row) for row in models],
        "limitations": [row["value"] for row in limitation_rows],
    }
