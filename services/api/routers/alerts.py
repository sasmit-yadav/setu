from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis

from services.api import config_repo
from services.api.deps import get_conn, get_idempotency_key, get_redis
from services.api.schemas import (
    AlertDetailOut,
    AlertSummaryOut,
    ApproveRequest,
    ApproveResponse,
    AssuranceOut,
    CreateAlertRequest,
    CreateAlertResponse,
    DeliveryRowOut,
    DispatchResponse,
    NewVersionRequest,
    NewVersionResponse,
    PreviewResponse,
    RuleResultOut,
    ValidateResponse,
)
from services.delivery.assurance_ladder import alert_assurance
from services.delivery.engine import DispatchError, QualityGateBlocked, dispatch_alert
from services.governance.approvals import (
    ApprovalError,
    approval_count,
    approve,
    required_count,
)
from services.governance.composer import (
    ComposeError,
    create_draft_alert,
    preview_exposure,
)
from services.governance.quality_gate import (
    has_blocking_failure,
    persist_results,
    validate,
)
from services.governance.versioning import VersionInFlightError, create_new_version

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.post("", response_model=CreateAlertResponse)
async def create_alert(
    body: CreateAlertRequest,
    conn: asyncpg.Connection = Depends(get_conn),
) -> CreateAlertResponse:
    try:
        result = await create_draft_alert(
            conn,
            severity=body.severity,
            headline=body.headline,
            body=body.body,
            lang=body.lang,
            unit_ids=body.unit_ids,
            geojson=body.geojson,
            point_lon=body.point_lon,
            point_lat=body.point_lat,
            effective_at=body.effective_at,
            expires_at=body.expires_at,
            estimated_onset_at=body.estimated_onset_at,
        )
    except ComposeError as exc:
        raise HTTPException(status_code=422, detail={"error": exc.code, "message": exc.message}) from exc
    return CreateAlertResponse(**result)


@router.get("", response_model=list[AlertSummaryOut])
async def list_alerts(
    lifecycle_status: str | None = None,
    severity: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    conn: asyncpg.Connection = Depends(get_conn),
) -> list[AlertSummaryOut]:
    effective_limit = limit if limit is not None else await config_repo.get_int(conn, "api.list_default_limit")
    rows = await conn.fetch(
        """
        SELECT id, incident_id, source_id, severity, headline, lifecycle_status,
               effective_at, expires_at
        FROM alert
        WHERE ($1::text IS NULL OR lifecycle_status = $1)
          AND ($2::text IS NULL OR severity = $2)
        ORDER BY effective_at DESC
        LIMIT $3 OFFSET $4
        """,
        lifecycle_status,
        severity,
        effective_limit,
        offset,
    )
    return [
        AlertSummaryOut(
            id=row["id"],
            incident_id=row["incident_id"],
            source_id=row["source_id"],
            severity=row["severity"],
            headline=row["headline"],
            lifecycle_status=row["lifecycle_status"],
            effective_at=row["effective_at"].isoformat(),
            expires_at=row["expires_at"].isoformat() if row["expires_at"] else None,
        )
        for row in rows
    ]


@router.get("/{alert_id}", response_model=AlertDetailOut)
async def get_alert(
    alert_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
) -> AlertDetailOut:
    row = await conn.fetchrow(
        """
        SELECT id, incident_id, source_id, severity, headline, body, lang,
               lifecycle_status, version_number, effective_at, expires_at
        FROM alert WHERE id = $1
        """,
        alert_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="alert_not_found")
    target_count = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT r.id)
        FROM recipient r
        JOIN admin_unit u ON u.id = r.unit_id
        JOIN alert a ON a.id = $1
        WHERE ST_Intersects(u.geom, a.area)
          AND r.consented_at IS NOT NULL
          AND r.opted_out_at IS NULL
        """,
        alert_id,
    )
    return AlertDetailOut(
        id=row["id"],
        incident_id=row["incident_id"],
        source_id=row["source_id"],
        severity=row["severity"],
        headline=row["headline"],
        body=row["body"],
        lang=row["lang"],
        lifecycle_status=row["lifecycle_status"],
        version_number=row["version_number"],
        effective_at=row["effective_at"].isoformat(),
        expires_at=row["expires_at"].isoformat() if row["expires_at"] else None,
        target_count=int(target_count or 0),
    )


@router.post("/{alert_id}/preview", response_model=PreviewResponse)
async def preview_alert(
    alert_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
) -> PreviewResponse:
    try:
        payload = await preview_exposure(conn, alert_id)
    except ComposeError as exc:
        raise HTTPException(status_code=404, detail=exc.code) from exc
    return PreviewResponse(**payload)


@router.post("/{alert_id}/validate", response_model=ValidateResponse)
async def validate_alert(
    alert_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
) -> ValidateResponse:
    exists = await conn.fetchval("SELECT 1 FROM alert WHERE id = $1", alert_id)
    if not exists:
        raise HTTPException(status_code=404, detail="alert_not_found")
    results = await validate(conn, alert_id)
    await persist_results(conn, alert_id, results)
    return ValidateResponse(
        alert_id=alert_id,
        results=[RuleResultOut(rule_id=r.rule_id, status=r.status, message=r.message) for r in results],
        blocked=has_blocking_failure(results),
    )


@router.post("/{alert_id}/approve", response_model=ApproveResponse)
async def approve_alert(
    alert_id: int,
    body: ApproveRequest,
    conn: asyncpg.Connection = Depends(get_conn),
) -> ApproveResponse:
    exists = await conn.fetchval("SELECT 1 FROM alert WHERE id = $1", alert_id)
    if not exists:
        raise HTTPException(status_code=404, detail="alert_not_found")
    severity = await conn.fetchval("SELECT severity FROM alert WHERE id = $1", alert_id)
    await approve(conn, alert_id, body.approver_id, reason=body.reason)
    have = await approval_count(conn, alert_id)
    need = await required_count(conn, severity)
    return ApproveResponse(alert_id=alert_id, have=have, need=need)


@router.post("/{alert_id}/dispatch", response_model=DispatchResponse)
async def dispatch(
    alert_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
    redis: Redis = Depends(get_redis),
    idempotency_key: str | None = Depends(get_idempotency_key),
) -> DispatchResponse:
    exists = await conn.fetchval("SELECT 1 FROM alert WHERE id = $1", alert_id)
    if not exists:
        raise HTTPException(status_code=404, detail="alert_not_found")
    if idempotency_key:
        cached = await redis.get(f"setu:idempotency:dispatch:{idempotency_key}")
        if cached:
            import json
            payload = json.loads(cached)
            return DispatchResponse(**payload)
    try:
        result = await dispatch_alert(conn, redis, alert_id, actor="api")
    except QualityGateBlocked as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_failed",
                "code": "quality_gate",
                "failures": exc.failures,
            },
        ) from exc
    except ApprovalError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "awaiting_authorization",
                "code": "approval_quorum",
                **exc.detail,
            },
        ) from exc
    except DispatchError as exc:
        raise HTTPException(status_code=422, detail={"error": exc.code, "message": exc.message}) from exc
    except VersionInFlightError as exc:
        retry_ms = await config_repo.get_int(conn, "api.version_conflict_retry_after_ms")
        raise HTTPException(
            status_code=409,
            detail={
                "error": "version_in_flight",
                "code": "supersede_locked",
                "retry_after_ms": retry_ms,
            },
        ) from exc
    response = DispatchResponse(**result)
    if idempotency_key:
        import json

        ttl = await config_repo.get_int(conn, "api.idempotency_ttl_seconds")
        await redis.set(
            f"setu:idempotency:dispatch:{idempotency_key}",
            json.dumps(result),
            ex=ttl,
        )
    return response


@router.post("/{alert_id}/new-version", response_model=NewVersionResponse)
async def new_version(
    alert_id: int,
    body: NewVersionRequest,
    conn: asyncpg.Connection = Depends(get_conn),
) -> NewVersionResponse:
    exists = await conn.fetchval("SELECT 1 FROM alert WHERE id = $1", alert_id)
    if not exists:
        raise HTTPException(status_code=404, detail="alert_not_found")
    try:
        new_id = await create_new_version(
            conn,
            alert_id,
            change_reason=body.change_reason,
            severity=body.severity,
            headline=body.headline,
            body=body.body,
            expires_at=body.expires_at,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="alert_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)}) from exc
    version_number = await conn.fetchval(
        "SELECT version_number FROM alert WHERE id = $1",
        new_id,
    )
    incident_id = await conn.fetchval(
        "SELECT incident_id FROM alert WHERE id = $1",
        new_id,
    )
    return NewVersionResponse(
        alert_id=new_id,
        incident_id=int(incident_id),
        version_number=int(version_number),
        supersedes_alert_id=alert_id,
    )


@router.get("/{alert_id}/assurance", response_model=AssuranceOut)
async def alert_assurance_view(
    alert_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
) -> AssuranceOut:
    exists = await conn.fetchval("SELECT 1 FROM alert WHERE id = $1", alert_id)
    if not exists:
        raise HTTPException(status_code=404, detail="alert_not_found")
    payload = await alert_assurance(conn, alert_id)
    return AssuranceOut(**payload)


@router.get("/{alert_id}/deliveries", response_model=list[DeliveryRowOut])
async def alert_deliveries(
    alert_id: int,
    limit: int | None = None,
    offset: int = 0,
    conn: asyncpg.Connection = Depends(get_conn),
) -> list[DeliveryRowOut]:
    exists = await conn.fetchval("SELECT 1 FROM alert WHERE id = $1", alert_id)
    if not exists:
        raise HTTPException(status_code=404, detail="alert_not_found")
    effective_limit = limit if limit is not None else await config_repo.get_int(conn, "api.list_default_limit")
    rows = await conn.fetch(
        """
        SELECT d.id, d.recipient_id, c.code AS channel_code, d.state, d.simulated,
               assurance_level(d.id) AS assurance_level
        FROM delivery d
        JOIN channel c ON c.id = d.channel_id
        WHERE d.alert_id = $1
        ORDER BY d.id
        LIMIT $2 OFFSET $3
        """,
        alert_id,
        effective_limit,
        offset,
    )
    return [
        DeliveryRowOut(
            id=row["id"],
            recipient_id=row["recipient_id"],
            channel_code=row["channel_code"],
            state=row["state"],
            simulated=row["simulated"],
            assurance_level=int(row["assurance_level"]),
        )
        for row in rows
    ]
