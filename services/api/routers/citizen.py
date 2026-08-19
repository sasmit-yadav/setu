from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.api.deps import get_conn

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


@router.get("/deliveries/{delivery_id}", response_model=CitizenDeliveryOut)
async def citizen_delivery(
    delivery_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
) -> CitizenDeliveryOut:
    row = await conn.fetchrow(
        """
        SELECT d.id, d.alert_id, a.headline, a.body, a.severity,
               c.code AS channel_code, d.simulated, a.lifecycle_status
        FROM delivery d
        JOIN alert a ON a.id = d.alert_id
        JOIN channel c ON c.id = d.channel_id
        WHERE d.id = $1
        """,
        delivery_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="delivery_not_found")
    return CitizenDeliveryOut(
        delivery_id=row["id"],
        alert_id=row["alert_id"],
        headline=row["headline"],
        body=row["body"],
        severity=row["severity"],
        channel_code=row["channel_code"],
        simulated=row["simulated"],
        lifecycle_status=row["lifecycle_status"],
    )
