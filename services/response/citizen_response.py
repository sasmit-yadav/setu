from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import asyncpg

from services.api import config_repo
from services.audit.ledger import append_audit
from services.delivery.assurance import record
from services.response.assistance_queue import create_case
from services.response.priority import compute_priority

RESPONSE_TYPES = frozenset({"safe", "trapped", "medical", "unable_to_evacuate", "other"})
ASSISTANCE_TYPES = frozenset({"trapped", "medical", "unable_to_evacuate", "other"})


class ResponseError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def _proximity(
    conn: asyncpg.Connection,
    *,
    unit_id: int,
    alert_id: int,
    location: tuple[float, float] | None,
) -> float:
    max_m = await config_repo.get_float(conn, "assistance.proximity_max_m")
    lon, lat = location if location else (None, None)
    value = await conn.fetchval(
        """
        SELECT GREATEST(
            0,
            1 - ST_Distance(
                COALESCE(
                    CASE WHEN $1::float8 IS NOT NULL
                         THEN ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
                    END,
                    u.centroid
                ),
                ST_Centroid(a.area)::geography
            ) / $3
        )
        FROM admin_unit u, alert a
        WHERE u.id = $4 AND a.id = $5
        """,
        lon,
        lat,
        max_m,
        unit_id,
        alert_id,
    )
    return float(value or 0.0)


async def _vulnerability(conn: asyncpg.Connection, unit_id: int) -> float:
    value = await conn.fetchval(
        "SELECT terrain_ruggedness FROM unit_features WHERE unit_id = $1",
        unit_id,
    )
    if value is None:
        return await config_repo.get_float(conn, "assistance.default_vulnerability")
    return float(value)


async def submit_response(
    conn: asyncpg.Connection,
    *,
    delivery_id: int,
    response_type: str,
    idempotency_key: str,
    free_text: str | None = None,
    location: tuple[float, float] | None = None,
    location_consent: bool = False,
    submitted_at: datetime | None = None,
) -> dict[str, Any]:
    if response_type not in RESPONSE_TYPES:
        raise ResponseError("invalid_response_type", f"Unknown response type {response_type}")
    if response_type == "other" and not free_text:
        raise ResponseError("free_text_required", "free_text is required for response type other")
    if location is not None and not location_consent:
        raise ResponseError("location_consent_required", "location_consent must be true when location is set")

    existing = await conn.fetchrow(
        """
        SELECT cr.id, cr.response_type, ac.id AS case_id
        FROM citizen_response cr
        LEFT JOIN assistance_case ac ON ac.citizen_response_id = cr.id
        WHERE cr.idempotency_key = $1
        """,
        idempotency_key,
    )
    if existing:
        return {
            "citizen_response_id": existing["id"],
            "response_type": existing["response_type"],
            "assistance_case_id": existing["case_id"],
            "duplicate": True,
        }

    delivery = await conn.fetchrow(
        """
        SELECT d.id, d.alert_id, r.unit_id, a.severity
        FROM delivery d
        JOIN recipient r ON r.id = d.recipient_id
        JOIN alert a ON a.id = d.alert_id
        WHERE d.id = $1
        """,
        delivery_id,
    )
    if delivery is None:
        raise ResponseError("delivery_not_found", "Delivery not found")

    received_at = datetime.now(UTC)
    submitted = submitted_at or received_at
    lon, lat = location if location else (None, None)
    response_id = await conn.fetchval(
        """
        INSERT INTO citizen_response (
            delivery_id, alert_id, unit_id, response_type, free_text,
            location, location_consent, idempotency_key, submitted_at, received_at
        )
        VALUES (
            $1, $2, $3, $4, $5,
            CASE WHEN $6::float8 IS NOT NULL
                 THEN ST_SetSRID(ST_MakePoint($6, $7), 4326)::geography
            END,
            $8, $9, $10, $11
        )
        RETURNING id
        """,
        delivery_id,
        delivery["alert_id"],
        delivery["unit_id"],
        response_type,
        free_text,
        lon,
        lat,
        location_consent,
        idempotency_key,
        submitted,
        received_at,
    )

    await record(
        conn,
        delivery_id,
        "citizen_response",
        source="citizen",
        metadata={"response_type": response_type},
    )

    incident_id = await conn.fetchval(
        "SELECT incident_id FROM alert WHERE id = $1",
        delivery["alert_id"],
    )
    await append_audit(
        conn,
        alert_id=delivery["alert_id"],
        delivery_id=delivery_id,
        incident_id=incident_id,
        event_type="citizen.response_received",
        payload={"response_type": response_type, "citizen_response_id": response_id},
        actor="citizen",
    )

    case_id = None
    if response_type in ASSISTANCE_TYPES:
        wait_minutes = max(
            (received_at - submitted).total_seconds()
            / await config_repo.get_float(conn, "time.seconds_per_minute"),
            0.0,
        )
        proximity = await _proximity(
            conn,
            unit_id=delivery["unit_id"],
            alert_id=delivery["alert_id"],
            location=location,
        )
        vulnerability = await _vulnerability(conn, delivery["unit_id"])
        score, factors = await compute_priority(
            conn,
            response_severity=response_type,
            hazard_severity=delivery["severity"],
            vulnerability=vulnerability,
            proximity=proximity,
            wait_minutes=wait_minutes,
        )
        case_id = await create_case(
            conn,
            citizen_response_id=int(response_id),
            priority_score=score,
            priority_factors=factors,
        )

    return {
        "citizen_response_id": int(response_id),
        "response_type": response_type,
        "assistance_case_id": case_id,
        "duplicate": False,
    }


async def record_from_dtmf(
    conn: asyncpg.Connection,
    delivery_id: int,
    digits: str,
) -> dict[str, Any] | None:
    safe_digit = await config_repo.get_str(conn, "ivr.dtmf.safe")
    need_help_digit = await config_repo.get_str(conn, "ivr.dtmf.need_help")
    trapped_digit = await config_repo.get_str(conn, "ivr.dtmf.trapped")
    medical_digit = await config_repo.get_str(conn, "ivr.dtmf.medical")
    evac_digit = await config_repo.get_str(conn, "ivr.dtmf.unable_to_evacuate")
    token = digits.strip()
    if token == safe_digit:
        response_type = "safe"
    elif token == trapped_digit:
        response_type = "trapped"
    elif token == medical_digit:
        response_type = "medical"
    elif token == evac_digit:
        response_type = "unable_to_evacuate"
    elif token == need_help_digit:
        return None
    else:
        response_type = "other"
    key = f"dtmf-{delivery_id}-{token}"
    return await submit_response(
        conn,
        delivery_id=delivery_id,
        response_type=response_type,
        idempotency_key=key,
    )
