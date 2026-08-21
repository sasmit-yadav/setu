from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from services.api.deps import get_conn
from services.api.settings import settings
from services.crypto.alert_signing import public_key_b64

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/signing-key")
async def signing_key() -> dict[str, str]:
    try:
        return {"public_key_b64": public_key_b64()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="signing_not_configured") from exc


@router.get("/config")
async def public_config(conn: asyncpg.Connection = Depends(get_conn)) -> dict[str, str | int | float]:
    keys = [
        "pwa.network_timeout_seconds",
        "pwa.alert_cache_max_age_seconds",
        "pwa.ack_retention_minutes",
        "pwa.receipt_retention_minutes",
        "response.free_text_max_chars",
        "response.help_types",
        "response.location_prompt_types",
        "response.free_text_types",
        "response.geolocation_timeout_ms",
        "response.safe_type",
        "api.list_default_limit",
        "api.deliveries_list_limit",
        "ui.ladder_extra_sample",
        "reachability.reached_tier_floor",
        "reachability.acknowledged_tier_floor",
        "map.tile_source",
        "map.openfreemap_style_url",
        "map.india_min_lon",
        "map.india_min_lat",
        "map.india_max_lon",
        "map.india_max_lat",
        "map.default_zoom",
        "map.pmtiles_min_bytes",
        "assistance.status_sequence",
        "relay.peer_enabled",
        "relay.peer_max_hops",
        "relay.peer_chunk_bytes",
        "relay.peer_service_uuid",
        "relay.peer_char_uuid",
        "translation.fallback_notice",
        "demo.citizen_email",
    ]
    rows = await conn.fetch(
        """
        SELECT key, value FROM app_config
        WHERE key = ANY($1::text[]) OR key LIKE 'response.label.%'
        """,
        keys,
    )
    out: dict[str, str | int | float] = {}
    for row in rows:
        value = row["value"]
        try:
            out[row["key"]] = int(value)
        except ValueError:
            try:
                out[row["key"]] = float(value)
            except ValueError:
                out[row["key"]] = value
    # Firebase web config is per-environment infra, not business policy, so it
    # comes from settings/env rather than app_config (§ same reasoning as
    # hf_space_url). Omitted entirely when unset, so the PWA's own check for
    # "is push configured" is just whether the key is present.
    if settings.firebase_api_key:
        out["firebase.api_key"] = settings.firebase_api_key
        out["firebase.project_id"] = settings.firebase_project_id
        out["firebase.messaging_sender_id"] = settings.firebase_messaging_sender_id
        out["firebase.app_id"] = settings.firebase_app_id
        out["firebase.vapid_public_key"] = settings.firebase_vapid_public_key
    return out
