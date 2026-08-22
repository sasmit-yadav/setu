from __future__ import annotations

import json

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from services.api import config_repo
from services.api.auth import Principal
from services.api.deps import get_conn
from services.api.rbac import (
    AUDITOR,
    assert_unit_in_scope,
    require_assistance_read,
    require_officer,
    require_relay_summary,
)
from services.api.schemas import (
    AssignCaseRequest,
    AssistanceCaseOut,
    AssistanceSummaryRow,
    PatchCaseRequest,
)
from services.response.assistance_queue import (
    advance_status,
    assign_case,
    get_case,
    list_cases,
)

router = APIRouter(prefix="/api/v1/assistance", tags=["assistance"])


def _scope_unit(principal: Principal) -> int | None:
    if principal.role in ("state_admin", "auditor"):
        return None
    return principal.unit_scope_id


def _case_out(row: dict, *, include_pii: bool) -> AssistanceCaseOut:
    factors = row["priority_factors"]
    if isinstance(factors, str):
        factors = json.loads(factors)
    lat = row.get("lat")
    lon = row.get("lon")
    return AssistanceCaseOut(
        id=row["id"],
        citizen_response_id=row["citizen_response_id"] if include_pii else None,
        priority_score=float(row["priority_score"]),
        priority_factors=factors,
        model_version=row["model_version"],
        status=row["status"],
        assigned_team=row.get("assigned_team"),
        response_type=row["response_type"],
        alert_id=row["alert_id"],
        unit_id=row["unit_id"],
        unit_name=row["unit_name"],
        free_text=row.get("free_text") if include_pii else None,
        lat=float(lat) if include_pii and lat is not None else None,
        lon=float(lon) if include_pii and lon is not None else None,
        channel_code=row["channel_code"],
    )


@router.get("/summary", response_model=list[AssistanceSummaryRow])
async def assistance_summary(
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_relay_summary),
) -> list[AssistanceSummaryRow]:
    rows = await conn.fetch(
        """
        SELECT cr.unit_id, u.name AS unit_name, COUNT(*)::int AS open_count
        FROM assistance_case ac
        JOIN citizen_response cr ON cr.id = ac.citizen_response_id
        JOIN admin_unit u ON u.id = cr.unit_id
        WHERE ac.status = 'new'
          AND (
            $1::bigint IS NULL
            OR cr.unit_id IN (
                WITH RECURSIVE descendants AS (
                    SELECT id FROM admin_unit WHERE id = $1
                    UNION ALL
                    SELECT child.id FROM admin_unit child
                    JOIN descendants d ON child.parent_id = d.id
                )
                SELECT id FROM descendants
            )
          )
        GROUP BY cr.unit_id, u.name
        ORDER BY open_count DESC, u.name
        """,
        _scope_unit(principal),
    )
    return [
        AssistanceSummaryRow(
            unit_id=row["unit_id"],
            unit_name=row["unit_name"],
            open_count=row["open_count"],
        )
        for row in rows
    ]


@router.get("", response_model=list[AssistanceCaseOut])
async def list_assistance_cases(
    status: str | None = "new",
    limit: int | None = None,
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_assistance_read),
) -> list[AssistanceCaseOut]:
    effective_limit = limit if limit is not None else await config_repo.get_int(conn, "api.list_default_limit")
    filter_status = None if status in (None, "all") else status
    rows = await list_cases(
        conn,
        status=filter_status,
        limit=effective_limit,
        scope_unit_id=_scope_unit(principal),
    )
    include_pii = principal.role != AUDITOR
    return [_case_out(row, include_pii=include_pii) for row in rows]


@router.get("/{case_id}", response_model=AssistanceCaseOut)
async def get_assistance_case(
    case_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_assistance_read),
) -> AssistanceCaseOut:
    row = await get_case(conn, case_id)
    if row is None:
        raise HTTPException(status_code=404, detail="case_not_found")
    await assert_unit_in_scope(conn, principal, row["unit_id"])
    return _case_out(row, include_pii=principal.role != AUDITOR)


@router.post("/{case_id}/assign", response_model=AssistanceCaseOut)
async def assign_assistance_case(
    case_id: int,
    body: AssignCaseRequest,
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_officer),
) -> AssistanceCaseOut:
    existing = await get_case(conn, case_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="case_not_found")
    await assert_unit_in_scope(conn, principal, existing["unit_id"])
    try:
        row = await assign_case(
            conn,
            case_id,
            assigned_team=body.assigned_team,
            assigned_by=principal.user_id,
            actor=principal.email,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="case_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    return _case_out(row, include_pii=True)


@router.patch("/{case_id}", response_model=AssistanceCaseOut)
async def patch_assistance_case(
    case_id: int,
    body: PatchCaseRequest,
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_officer),
) -> AssistanceCaseOut:
    existing = await get_case(conn, case_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="case_not_found")
    await assert_unit_in_scope(conn, principal, existing["unit_id"])
    sequence = await config_repo.get_csv(conn, "assistance.status_sequence")
    try:
        row = await advance_status(
            conn,
            case_id,
            next_status=body.status,
            assigned_team=body.assigned_team,
            assigned_by=principal.user_id,
            actor=principal.email,
            sequence=sequence,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="case_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    return _case_out(row, include_pii=True)
