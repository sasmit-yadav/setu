from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from services.api import config_repo


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    status: str
    message: str | None = None


async def _geometry_non_empty(conn: asyncpg.Connection, alert_id: int) -> RuleResult:
    empty = await conn.fetchval(
        """
        SELECT ST_IsEmpty(area) OR ST_Area(area::geography) = 0
        FROM alert WHERE id = $1
        """,
        alert_id,
    )
    if empty:
        return RuleResult("geometry_non_empty", "fail", "Alert area geometry is empty")
    return RuleResult("geometry_non_empty", "pass", None)


async def _expiry_set(conn: asyncpg.Connection, alert_id: int) -> RuleResult:
    require = await config_repo.get_bool(conn, "quality_gate.require_expiry")
    if not require:
        return RuleResult("expiry_set", "pass", None)
    expires_at = await conn.fetchval(
        "SELECT expires_at FROM alert WHERE id = $1",
        alert_id,
    )
    if expires_at is None:
        return RuleResult("expiry_set", "fail", "No expiry timestamp set")
    return RuleResult("expiry_set", "pass", None)


async def _target_count_plausible(conn: asyncpg.Connection, alert_id: int) -> RuleResult:
    minimum = await config_repo.get_int(conn, "quality_gate.min_target_count")
    count = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT r.id)
        FROM recipient r
        JOIN admin_unit u ON r.unit_id = u.id
        JOIN alert a ON a.id = $1
        WHERE ST_Intersects(u.geom, a.area)
          AND r.consented_at IS NOT NULL
        """,
        alert_id,
    )
    if count < minimum:
        return RuleResult(
            "target_count_plausible",
            "fail",
            f"Target count {count} is below minimum {minimum}",
        )
    return RuleResult("target_count_plausible", "pass", None)


async def _escalation_policy_exists(conn: asyncpg.Connection, alert_id: int) -> RuleResult:
    severity = await conn.fetchval("SELECT severity FROM alert WHERE id = $1", alert_id)
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM escalation_policy WHERE severity = $1",
        severity,
    )
    if count == 0:
        return RuleResult(
            "escalation_policy_exists",
            "fail",
            f"No escalation policy for severity {severity}",
        )
    return RuleResult("escalation_policy_exists", "pass", None)


async def _case_study_states(conn: asyncpg.Connection, alert_id: int) -> list[str]:
    rows = await conn.fetch(
        "SELECT key, value FROM app_config WHERE key LIKE 'case_study.bbox.%'"
    )
    states: list[str] = []
    for row in rows:
        state = str(row["key"]).rsplit(".", 1)[-1]
        south, west, north, east = (float(part) for part in str(row["value"]).split(","))
        intersects = await conn.fetchval(
            """
            SELECT ST_Intersects(
                a.area,
                ST_MakeEnvelope($1, $2, $3, $4, 4326)
            )
            FROM alert a WHERE a.id = $5
            """,
            west,
            south,
            east,
            north,
            alert_id,
        )
        if intersects:
            states.append(state)
    return states


async def _translation_exists(conn: asyncpg.Connection, alert_id: int) -> RuleResult:
    severity = await conn.fetchval("SELECT severity FROM alert WHERE id = $1", alert_id)
    if severity not in {"severe", "extreme"}:
        return RuleResult("translation_exists", "pass", None)
    states = await _case_study_states(conn, alert_id)
    if not states:
        return RuleResult("translation_exists", "pass", None)
    missing: list[str] = []
    for state in states:
        key = f"quality_gate.required_lang_for_{severity}.{state}"
        required_lang = await config_repo.get(conn, key)
        if not required_lang:
            continue
        has = await conn.fetchval(
            "SELECT 1 FROM alert_translation WHERE alert_id = $1 AND lang = $2",
            alert_id,
            required_lang,
        )
        if not has:
            missing.append(f"{required_lang} ({state})")
    if missing:
        return RuleResult(
            "translation_exists",
            "fail",
            f"Missing translations: {', '.join(missing)}",
        )
    return RuleResult("translation_exists", "pass", None)


async def _target_area_plausible(conn: asyncpg.Connection, alert_id: int) -> RuleResult:
    max_km2 = await config_repo.get_float(conn, "quality_gate.max_target_area_km2")
    area_km2 = await conn.fetchval(
        """
        SELECT ST_Area(area::geography) / 1000000.0
        FROM alert WHERE id = $1
        """,
        alert_id,
    )
    if area_km2 is not None and float(area_km2) > max_km2:
        return RuleResult(
            "target_area_plausible",
            "warn",
            f"Target area {float(area_km2):.0f} km² exceeds {max_km2:.0f} km² threshold",
        )
    return RuleResult("target_area_plausible", "pass", None)


RULES = (
    _geometry_non_empty,
    _expiry_set,
    _target_count_plausible,
    _escalation_policy_exists,
    _translation_exists,
    _target_area_plausible,
)


async def validate(conn: asyncpg.Connection, alert_id: int) -> list[RuleResult]:
    results: list[RuleResult] = []
    for rule in RULES:
        results.append(await rule(conn, alert_id))
    return results


async def persist_results(
    conn: asyncpg.Connection, alert_id: int, results: list[RuleResult]
) -> None:
    for result in results:
        await conn.execute(
            """
            INSERT INTO alert_validation_result (alert_id, rule_id, status, message)
            VALUES ($1, $2, $3, $4)
            """,
            alert_id,
            result.rule_id,
            result.status,
            result.message,
        )


def has_blocking_failure(results: list[RuleResult]) -> bool:
    return any(r.status == "fail" for r in results)
