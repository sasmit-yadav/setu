from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends

from services.api.auth import Principal
from services.api.deps import get_conn
from services.api.rbac import require_operational_read

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/lead-time")
async def lead_time(
    conn: asyncpg.Connection = Depends(get_conn),
    _principal: Principal = Depends(require_operational_read),
) -> dict:
    coverage = await conn.fetchrow("SELECT * FROM v_lead_time_coverage")
    percentiles = await conn.fetchrow(
        """
        SELECT
            percentile_cont(0.10) WITHIN GROUP (ORDER BY lead_time_minutes) AS p10,
            percentile_cont(0.50) WITHIN GROUP (ORDER BY lead_time_minutes) AS p50,
            percentile_cont(0.90) WITHIN GROUP (ORDER BY lead_time_minutes) AS p90
        FROM v_lead_time
        """
    )
    seismic = await conn.fetchval(
        """
        SELECT COUNT(*) FROM alert
        WHERE source_id = 'usgs'
          AND lifecycle_status IN ('active', 'superseded', 'resolved')
        """
    )
    return {
        "p10": float(percentiles["p10"]) if percentiles and percentiles["p10"] is not None else None,
        "p50": float(percentiles["p50"]) if percentiles and percentiles["p50"] is not None else None,
        "p90": float(percentiles["p90"]) if percentiles and percentiles["p90"] is not None else None,
        "coverage_pct": float(coverage["coverage_pct"]) if coverage and coverage["coverage_pct"] is not None else 0.0,
        "alerts_with_onset": int(coverage["alerts_with_onset"] or 0) if coverage else 0,
        "alerts_total": int(coverage["alerts_total"] or 0) if coverage else 0,
        "excluded_seismic_count": int(seismic or 0),
        "exclusion_reason": (
            "USGS earthquakes have no forecast onset — lead time is not applicable "
            "and is excluded from percentiles."
        ),
    }
