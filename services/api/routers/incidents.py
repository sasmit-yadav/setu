from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from services.api.deps import get_conn
from services.api.schemas import IncidentDetailOut, TimelineEventOut
from services.audit.timeline import incident_detail, incident_timeline

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.get("/{incident_id}", response_model=IncidentDetailOut)
async def get_incident(
    incident_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
) -> IncidentDetailOut:
    detail = await incident_detail(conn, incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="incident_not_found")
    for version in detail["versions"]:
        if version.get("effective_at"):
            version["effective_at"] = version["effective_at"].isoformat()
        if version.get("expires_at"):
            version["expires_at"] = version["expires_at"].isoformat()
    return IncidentDetailOut(**detail)


@router.get("/{incident_id}/timeline", response_model=list[TimelineEventOut])
async def get_incident_timeline(
    incident_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
) -> list[TimelineEventOut]:
    exists = await conn.fetchval("SELECT 1 FROM incident WHERE id = $1", incident_id)
    if not exists:
        raise HTTPException(status_code=404, detail="incident_not_found")
    events = await incident_timeline(conn, incident_id)
    return [TimelineEventOut(**event) for event in events]
