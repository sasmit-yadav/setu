from __future__ import annotations

import pytest

from services.governance.quality_gate import has_blocking_failure, validate


async def _insert_incident(conn) -> int:
    return await conn.fetchval(
        """
        INSERT INTO incident (label, incident_type, status, origin_source)
        VALUES ('QG-INC', 'test', 'active', 'manual')
        RETURNING id
        """
    )


async def _insert_alert(
    conn,
    *,
    severity: str = "severe",
    expires_at: str | None = "now() + interval '2 hours'",
) -> int:
    unit_id = await conn.fetchval("SELECT id FROM admin_unit LIMIT 1")
    if unit_id is None:
        pytest.skip("admin_unit empty")
    incident_id = await _insert_incident(conn)
    expires_expr = "NULL" if expires_at is None else expires_at
    return await conn.fetchval(
        f"""
        INSERT INTO alert (
            source_id, severity, headline, body, lang, area,
            effective_at, expires_at, raw_checksum, incident_id, lifecycle_status
        )
        SELECT 'manual', $1, 'Headline', 'Body', 'en', geom,
               now(), {expires_expr}, 'checksum-{severity}', $2, 'draft'
        FROM admin_unit WHERE id = $3
        RETURNING id
        """,
        severity,
        incident_id,
        unit_id,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expiry_set_fails_without_expires_at(db_conn):
    alert_id = await _insert_alert(db_conn, expires_at=None)
    results = await validate(db_conn, alert_id)
    expiry = next(r for r in results if r.rule_id == "expiry_set")
    assert expiry.status == "fail"
    assert has_blocking_failure(results)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expiry_set_passes_with_expires_at(db_conn):
    alert_id = await _insert_alert(db_conn)
    results = await validate(db_conn, alert_id)
    expiry = next(r for r in results if r.rule_id == "expiry_set")
    assert expiry.status == "pass"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_escalation_policy_exists_fails_for_unknown_severity(db_conn):
    alert_id = await _insert_alert(db_conn, severity="unknown")
    results = await validate(db_conn, alert_id)
    rule = next(r for r in results if r.rule_id == "escalation_policy_exists")
    assert rule.status == "fail"
    assert has_blocking_failure(results)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_escalation_policy_exists_passes_for_severe(db_conn):
    alert_id = await _insert_alert(db_conn, severity="severe")
    results = await validate(db_conn, alert_id)
    rule = next(r for r in results if r.rule_id == "escalation_policy_exists")
    assert rule.status == "pass"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_translation_exists_fails_without_required_lang(db_conn):
    in_kl = await db_conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM app_config WHERE key = 'case_study.bbox.KL')"
    )
    if not in_kl:
        pytest.skip("case_study.bbox.KL not seeded — run python run.py seed")
    alert_id = await _insert_alert(db_conn, severity="severe")
    await db_conn.execute(
        """
        UPDATE alert
        SET area = ST_Buffer(ST_SetSRID(ST_MakePoint(76.0, 11.8), 4326)::geography, 500)::geometry
        WHERE id = $1
        """,
        alert_id,
    )
    results = await validate(db_conn, alert_id)
    rule = next(r for r in results if r.rule_id == "translation_exists")
    assert rule.status == "fail"
    assert "ml" in (rule.message or "")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_translation_exists_passes_with_malayalam(db_conn):
    in_kl = await db_conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM app_config WHERE key = 'case_study.bbox.KL')"
    )
    if not in_kl:
        pytest.skip("case_study.bbox.KL not seeded")
    alert_id = await _insert_alert(db_conn, severity="severe")
    await db_conn.execute(
        """
        UPDATE alert
        SET area = (
            SELECT ST_Buffer(ST_SetSRID(ST_MakePoint(76.0, 11.8), 4326)::geography, 500)::geometry
            FROM alert WHERE id = $1
        )
        WHERE id = $1
        """,
        alert_id,
    )
    await db_conn.execute(
        """
        INSERT INTO alert_translation (alert_id, lang, headline, body)
        VALUES ($1, 'ml', 'Malayalam headline', 'Malayalam body')
        """,
        alert_id,
    )
    results = await validate(db_conn, alert_id)
    rule = next(r for r in results if r.rule_id == "translation_exists")
    assert rule.status == "pass"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_target_area_plausible_warns_on_huge_polygon(db_conn):
    alert_id = await _insert_alert(db_conn, severity="moderate")
    await db_conn.execute(
        """
        UPDATE alert
        SET area = ST_Buffer(ST_SetSRID(ST_MakePoint(76.0, 11.8), 4326)::geography, 200000)::geometry
        WHERE id = $1
        """,
        alert_id,
    )
    results = await validate(db_conn, alert_id)
    rule = next(r for r in results if r.rule_id == "target_area_plausible")
    assert rule.status == "warn"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_target_area_plausible_passes_for_normal_polygon(db_conn):
    alert_id = await _insert_alert(db_conn, severity="moderate")
    results = await validate(db_conn, alert_id)
    rule = next(r for r in results if r.rule_id == "target_area_plausible")
    assert rule.status == "pass"
