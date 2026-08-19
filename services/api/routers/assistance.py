from __future__ import annotations

import json

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from services.api import config_repo
from services.api.deps import get_conn
from services.api.schemas import AssignCaseRequest, AssistanceCaseOut
from services.response.assistance_queue import assign_case, get_case, list_cases

router = APIRouter(prefix="/api/v1/assistance", tags=["assistance"])


def _case_out(row: dict) -> AssistanceCaseOut:
    factors = row["priority_factors"]
    if isinstance(factors, str):
        factors = json.loads(factors)
    return AssistanceCaseOut(
        id=row["id"],
        citizen_response_id=row["citizen_response_id"],
        priority_score=float(row["priority_score"]),
        priority_factors=factors,
        model_version=row["model_version"],
        status=row["status"],
        assigned_team=row.get("assigned_team"),
        response_type=row["response_type"],
        alert_id=row["alert_id"],
        unit_id=row["unit_id"],
        unit_name=row["unit_name"],
    )


@router.get("", response_model=list[AssistanceCaseOut])
async def list_assistance_cases(
    status: str = "new",
    limit: int | None = None,
    conn: asyncpg.Connection = Depends(get_conn),
) -> list[AssistanceCaseOut]:
    effective_limit = limit if limit is not None else await config_repo.get_int(conn, "api.list_default_limit")
    rows = await list_cases(conn, status=status, limit=effective_limit)
    return [_case_out(row) for row in rows]


@router.get("/{case_id}", response_model=AssistanceCaseOut)
async def get_assistance_case(
    case_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
) -> AssistanceCaseOut:
    row = await get_case(conn, case_id)
    if row is None:
        raise HTTPException(status_code=404, detail="case_not_found")
    return _case_out(row)


@router.post("/{case_id}/assign", response_model=AssistanceCaseOut)
async def assign_assistance_case(
    case_id: int,
    body: AssignCaseRequest,
    conn: asyncpg.Connection = Depends(get_conn),
) -> AssistanceCaseOut:
    try:
        row = await assign_case(
            conn,
            case_id,
            assigned_team=body.assigned_team,
            assigned_by=body.assigned_by,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="case_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    return _case_out(row)
