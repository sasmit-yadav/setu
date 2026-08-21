from __future__ import annotations

import json

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from services.api import config_repo
from services.api.auth import Principal
from services.api.deps import get_conn
from services.api.rbac import (
    RELAY_NODE,
    assert_unit_in_scope,
    optional_principal,
    require_operational_read,
)
from services.api.schemas import ReachabilityOut, UnitRiskOut, VulnerabilityOut

router = APIRouter(prefix="/api/v1/units", tags=["units"])


@router.get("")
async def list_units(
    q: str | None = None,
    limit: int | None = None,
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal | None = Depends(optional_principal),
) -> list[dict]:
    if principal is not None and principal.role == RELAY_NODE:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "code": "role"})
    effective_limit = limit if limit is not None else await config_repo.get_int(conn, "api.list_default_limit")
    rows = await conn.fetch(
        """
        SELECT id, name, level
        FROM admin_unit
        WHERE ($1::text IS NULL OR name ILIKE '%' || $1 || '%')
        ORDER BY level, name
        LIMIT $2
        """,
        q,
        effective_limit,
    )
    return [{"unit_id": row["id"], "name": row["name"], "level": row["level"]} for row in rows]


@router.get("/{unit_id}/reachability", response_model=ReachabilityOut)
async def unit_reachability(
    unit_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_operational_read),
) -> ReachabilityOut:
    await assert_unit_in_scope(conn, principal, unit_id)
    row = await conn.fetchrow(
        "SELECT * FROM v_reachability WHERE unit_id = $1",
        unit_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="unit_not_found")
    return ReachabilityOut(
        unit_id=row["unit_id"],
        name=row["name"],
        geometry_level=row["geometry_level"],
        estimated_population=row["estimated_population"],
        registered_recipients=row["registered_recipients"] or 0,
        reached_recipients=row["reached_recipients"] or 0,
        acknowledged_recipients=row["acknowledged_recipients"] or 0,
        unverified_recipients=row["unverified_recipients"] or 0,
        recipient_reach_pct=float(row["recipient_reach_pct"]) if row["recipient_reach_pct"] is not None else None,
        population_reach_pct=float(row["population_reach_pct"]) if row["population_reach_pct"] is not None else None,
        last_dispatch_at=row["last_dispatch_at"].isoformat() if row["last_dispatch_at"] else None,
    )


@router.get("/{unit_id}/vulnerability", response_model=VulnerabilityOut)
async def unit_vulnerability(
    unit_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_operational_read),
) -> VulnerabilityOut:
    await assert_unit_in_scope(conn, principal, unit_id)
    row = await conn.fetchrow(
        "SELECT * FROM v_communication_vulnerability WHERE unit_id = $1",
        unit_id,
    )
    if row is None:
        unit = await conn.fetchrow(
            """
            SELECT u.id, u.name, rv.recipient_reach_pct
            FROM admin_unit u
            LEFT JOIN v_reachability rv ON rv.unit_id = u.id
            WHERE u.id = $1
            """,
            unit_id,
        )
        if unit is None:
            raise HTTPException(status_code=404, detail="unit_not_found")
        return VulnerabilityOut(
            unit_id=unit["id"],
            name=unit["name"],
            tower_count_5km=None,
            nearest_tower_km=None,
            terrain_ruggedness=None,
            historical_reach_pct=float(unit["recipient_reach_pct"])
            if unit["recipient_reach_pct"] is not None
            else None,
            primary_factors=[],
            recommended_fallback="unknown_connectivity_features_pending",
        )
    return VulnerabilityOut(
        unit_id=row["unit_id"],
        name=row["name"],
        tower_count_5km=float(row["tower_count_5km"]) if row["tower_count_5km"] is not None else None,
        nearest_tower_km=float(row["nearest_tower_km"]) if row["nearest_tower_km"] is not None else None,
        terrain_ruggedness=float(row["terrain_ruggedness"]) if row["terrain_ruggedness"] is not None else None,
        historical_reach_pct=float(row["historical_reach_pct"]) if row["historical_reach_pct"] is not None else None,
        primary_factors=list(row["primary_factors"] or []),
        recommended_fallback=row["recommended_fallback"],
    )


@router.get("/{unit_id}/risk", response_model=UnitRiskOut)
async def unit_risk(
    unit_id: int,
    alert_id: int | None = None,
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal | None = Depends(optional_principal),
) -> UnitRiskOut:
    if principal is not None and principal.role == RELAY_NODE:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "code": "role"})
    if principal is not None:
        await assert_unit_in_scope(conn, principal, unit_id)
    unit = await conn.fetchrow("SELECT id FROM admin_unit WHERE id = $1", unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="unit_not_found")
    if alert_id is None:
        alert_id = await conn.fetchval(
            """
            SELECT a.id FROM alert a
            JOIN admin_unit u ON ST_Intersects(u.geom, a.area)
            WHERE u.id = $1 AND a.lifecycle_status = 'active'
            ORDER BY a.effective_at DESC
            LIMIT 1
            """,
            unit_id,
        )
    row = None
    if alert_id is not None:
        row = await conn.fetchrow(
            """
            SELECT rp.risk_score, rp.features, m.is_bootstrap, m.name, m.version
            FROM reach_prediction rp
            JOIN model_registry m ON m.id = rp.model_id
            WHERE rp.unit_id = $1 AND rp.alert_id = $2
            """,
            unit_id,
            alert_id,
        )
    if row is None:
        vuln = await conn.fetchrow(
            "SELECT recommended_fallback FROM v_communication_vulnerability WHERE unit_id = $1",
            unit_id,
        )
        return UnitRiskOut(
            unit_id=unit_id,
            alert_id=alert_id,
            risk_score=None,
            top_factors=[],
            recommended_action=vuln["recommended_fallback"] if vuln else None,
            is_bootstrap=True,
            disclosure=await config_repo.get_str(conn, "reach_risk.disclosure.missing"),
        )
    features = row["features"]
    if isinstance(features, str):
        features = json.loads(features)
    top_factors = []
    if isinstance(features, dict):
        for key, value in features.items():
            top_factors.append({"factor": key, "value": value})
    limit = await config_repo.get_int(conn, "risk.top_factors_limit")
    disclosure = (
        await config_repo.get_str(conn, "reach_risk.disclosure.bootstrap")
        if row["is_bootstrap"]
        else f"Model {row['name']} {row['version']}."
    )
    return UnitRiskOut(
        unit_id=unit_id,
        alert_id=alert_id,
        risk_score=float(row["risk_score"]),
        top_factors=top_factors[:limit],
        recommended_action=await conn.fetchval(
            "SELECT recommended_fallback FROM v_communication_vulnerability WHERE unit_id = $1",
            unit_id,
        ),
        is_bootstrap=bool(row["is_bootstrap"]),
        disclosure=disclosure,
    )
