from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.api import config_repo
from services.api.auth import Principal
from services.api.citizen_otp import recipient_id_for_principal
from services.api.deps import get_conn
from services.api.rbac import assert_delivery_in_scope, require_citizen_write
from services.api.schemas import DeviceRegisterRequest, DeviceRegisterResponse
from services.crypto.alert_signing import sign_payload
from services.delivery.fatigue import apply_headline
from services.ml.translate import lang_for_unit, resolve_alert_text

router = APIRouter(prefix="/api/v1/citizen", tags=["citizen"])


class CitizenDeliveryOut(BaseModel):
    delivery_id: int
    alert_id: int
    headline: str
    body: str
    severity: str
    channel_code: str
    simulated: bool
    lifecycle_status: str
    expires_at: str | None = None
    effective_at: str | None = None
    signature: str | None = None
    lang: str
    source_lang: str
    translated: bool = False
    fallback_notice: str | None = None


async def _to_out(
    conn: asyncpg.Connection,
    row: asyncpg.Record,
    *,
    lang: str | None = None,
) -> CitizenDeliveryOut:
    resolved = await resolve_alert_text(
        conn, row["alert_id"], lang or row["preferred_lang"]
    )
    headline, _ = await apply_headline(conn, row["alert_id"], resolved.headline)
    effective_at = row["effective_at"].isoformat() if row["effective_at"] else None
    signature = None
    if effective_at:
        signature = sign_payload(
            {
                "alert_id": row["alert_id"],
                "delivery_id": row["id"],
                "headline": headline,
                "severity": row["severity"],
                "effective_at": effective_at,
            }
        )
    return CitizenDeliveryOut(
        delivery_id=row["id"],
        alert_id=row["alert_id"],
        headline=headline,
        body=resolved.body,
        severity=row["severity"],
        channel_code=row["channel_code"],
        simulated=row["simulated"],
        lifecycle_status=row["lifecycle_status"],
        expires_at=row["expires_at"].isoformat() if row["expires_at"] else None,
        effective_at=effective_at,
        signature=signature,
        lang=resolved.lang,
        source_lang=resolved.source_lang,
        translated=resolved.translated,
        fallback_notice=resolved.fallback_notice,
    )


_DELIVERY_SELECT = """
        SELECT d.id, d.alert_id, a.headline, a.body, a.severity, a.lang AS source_lang,
               r.preferred_lang, c.code AS channel_code, d.simulated, a.lifecycle_status,
               a.expires_at, a.effective_at
        FROM delivery d
        JOIN alert a ON a.id = d.alert_id
        JOIN channel c ON c.id = d.channel_id
        JOIN recipient r ON r.id = d.recipient_id
"""


@router.get("/deliveries", response_model=list[CitizenDeliveryOut])
async def list_citizen_deliveries(
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_citizen_write),
) -> list[CitizenDeliveryOut]:
    if principal.unit_scope_id is None:
        return []
    village_lang = await lang_for_unit(conn, principal.unit_scope_id)
    cap = await config_repo.get_int(conn, "api.list_default_limit")
    own_id = await recipient_id_for_principal(conn, principal)
    if own_id is not None:
        rows = await conn.fetch(
            _DELIVERY_SELECT
            + """
            WHERE r.id = $1 AND a.lifecycle_status = 'active'
            ORDER BY a.effective_at DESC NULLS LAST, d.id DESC
            LIMIT $2
            """,
            own_id,
            cap,
        )
    else:
        rows = await conn.fetch(
            _DELIVERY_SELECT
            + """
            WHERE r.unit_id = $1 AND a.lifecycle_status = 'active'
            ORDER BY (r.kind = 'citizen_pwa') DESC,
                     a.effective_at DESC NULLS LAST, d.id DESC
            LIMIT $2
            """,
            principal.unit_scope_id,
            cap,
        )
    seen: set[int] = set()
    out: list[CitizenDeliveryOut] = []
    for row in rows:
        if row["alert_id"] in seen:
            continue
        seen.add(row["alert_id"])
        out.append(await _to_out(conn, row, lang=row["preferred_lang"] or village_lang))
    return out[:cap]


@router.get("/deliveries/{delivery_id}", response_model=CitizenDeliveryOut)
async def citizen_delivery(
    delivery_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_citizen_write),
) -> CitizenDeliveryOut:
    await assert_delivery_in_scope(conn, principal, delivery_id)
    row = await conn.fetchrow(_DELIVERY_SELECT + " WHERE d.id = $1", delivery_id)
    if row is None:
        raise HTTPException(status_code=404, detail="delivery_not_found")
    village_lang = (
        await lang_for_unit(conn, principal.unit_scope_id)
        if principal.unit_scope_id is not None
        else None
    )
    return await _to_out(conn, row, lang=row["preferred_lang"] or village_lang)


@router.post("/device", response_model=DeviceRegisterResponse)
async def register_device(
    body: DeviceRegisterRequest,
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_citizen_write),
) -> DeviceRegisterResponse:
    """Called once the PWA has a real FCM token (getToken() succeeded).

    Phone-OTP sessions bind the token onto that SIM's recipient row so the
    next Send can FCM *that* person. Email / officer sessions still upsert
    the one 'citizen_pwa' row per village.
    """
    if principal.unit_scope_id is None:
        raise HTTPException(status_code=400, detail="no_unit_scope_for_citizen")
    preferred = await lang_for_unit(conn, principal.unit_scope_id)
    own_id = await recipient_id_for_principal(conn, principal)
    if own_id is not None:
        row = await conn.fetchrow(
            """
            UPDATE recipient
            SET push_token = $2,
                consented_at = COALESCE(consented_at, now()),
                preferred_lang = COALESCE(preferred_lang, $3)
            WHERE id = $1
            RETURNING id, unit_id
            """,
            own_id,
            body.push_token,
            preferred,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="recipient_not_found")
        return DeviceRegisterResponse(recipient_id=row["id"], unit_id=row["unit_id"])
    row = await conn.fetchrow(
        """
        INSERT INTO recipient (
            unit_id, kind, push_token, preferred_lang, consented_at, consent_source
        )
        VALUES ($1, 'citizen_pwa', $2, $3, now(), 'pwa_push_opt_in')
        ON CONFLICT (unit_id) WHERE kind = 'citizen_pwa' DO UPDATE
            SET push_token = EXCLUDED.push_token,
                consented_at = now(),
                preferred_lang = COALESCE(recipient.preferred_lang, EXCLUDED.preferred_lang)
        RETURNING id, unit_id
        """,
        principal.unit_scope_id,
        body.push_token,
        preferred,
    )
    return DeviceRegisterResponse(recipient_id=row["id"], unit_id=row["unit_id"])


@router.get("/deliveries/{delivery_id}/safe-zone")
async def citizen_safe_zone(
    delivery_id: int,
    lat: float | None = None,
    lon: float | None = None,
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_citizen_write),
) -> dict:
    from services.api import config_repo

    await assert_delivery_in_scope(conn, principal, delivery_id)
    row = await conn.fetchrow(
        """
        SELECT d.id, d.alert_id, r.unit_id,
               ST_Y(ST_Centroid(u.geom::geometry)) AS unit_lat,
               ST_X(ST_Centroid(u.geom::geometry)) AS unit_lon
        FROM delivery d
        JOIN recipient r ON r.id = d.recipient_id
        JOIN admin_unit u ON u.id = r.unit_id
        WHERE d.id = $1
        """,
        delivery_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="delivery_not_found")
    origin_lat = lat if lat is not None else float(row["unit_lat"])
    origin_lon = lon if lon is not None else float(row["unit_lon"])
    limit = await config_repo.get_int(conn, "safe_zone.candidate_limit")
    candidates = await conn.fetch(
        """
        SELECT sz.id, sz.name, sz.kind,
               ST_Y(sz.geom::geometry) AS lat,
               ST_X(sz.geom::geometry) AS lon,
               ST_Distance(sz.geom, ST_SetSRID(ST_MakePoint($2, $3), 4326)::geography) AS meters
        FROM safe_zone sz
        WHERE sz.unit_id = $1 OR ST_DWithin(
            sz.geom,
            ST_SetSRID(ST_MakePoint($2, $3), 4326)::geography,
            $4
        )
        ORDER BY meters
        LIMIT $5
        """,
        row["unit_id"],
        origin_lon,
        origin_lat,
        await config_repo.get_float(conn, "safe_zone.search_radius_m"),
        limit,
    )
    for zone in candidates:
        crosses = await conn.fetchval(
            """
            SELECT ST_Intersects(
                ST_MakeLine(
                    ST_SetSRID(ST_MakePoint($1, $2), 4326),
                    ST_SetSRID(ST_MakePoint($3, $4), 4326)
                ),
                a.area::geometry
            )
            FROM alert a WHERE a.id = $5
            """,
            origin_lon,
            origin_lat,
            float(zone["lon"]),
            float(zone["lat"]),
            row["alert_id"],
        )
        if crosses:
            continue
        return {
            "safe_zone_id": zone["id"],
            "name": zone["name"],
            "kind": zone["kind"],
            "lat": float(zone["lat"]),
            "lon": float(zone["lon"]),
            "distance_m": float(zone["meters"]),
            "disclosure": "Route avoids the warning area. Road conditions are not included — we have no live source for them.",
        }
    raise HTTPException(status_code=404, detail="no_safe_zone")

