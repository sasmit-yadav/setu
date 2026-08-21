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


# ── geometry_non_empty and target_count_plausible ────────────────────────────
# Part 16 Day 5's DoD is "All 6 rules have a unit test with a passing and a
# failing fixture." These two were the gap: both are named in Day 4 as among the
# first three rules made real, but neither had a test in either direction, so a
# regression in the two oldest rules would not have been caught.


@pytest.mark.integration
@pytest.mark.asyncio
async def test_geometry_non_empty_fails_on_empty_geometry(db_conn):
    alert_id = await _insert_alert(db_conn)
    # A degenerate polygon: zero-area, so ST_Area(...) = 0 catches it even
    # though ST_IsEmpty() is false. Both halves of the rule's OR matter.
    await db_conn.execute(
        """
        UPDATE alert
        SET area = ST_Multi(ST_GeomFromText(
            'POLYGON((76 11, 76 11, 76 11, 76 11))', 4326))
        WHERE id = $1
        """,
        alert_id,
    )
    results = await validate(db_conn, alert_id)
    rule = next(r for r in results if r.rule_id == "geometry_non_empty")
    assert rule.status == "fail"
    assert rule.message == "Alert area geometry is empty"
    assert has_blocking_failure(results)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_geometry_non_empty_passes_for_real_unit_geometry(db_conn):
    alert_id = await _insert_alert(db_conn)
    results = await validate(db_conn, alert_id)
    rule = next(r for r in results if r.rule_id == "geometry_non_empty")
    assert rule.status == "pass"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_target_count_plausible_fails_when_no_recipients_intersect(db_conn):
    alert_id = await _insert_alert(db_conn)
    # Move the alert into the middle of the Indian Ocean: valid, non-empty
    # geometry that no admin_unit — and therefore no recipient — intersects.
    # This isolates target_count_plausible from geometry_non_empty.
    await db_conn.execute(
        """
        UPDATE alert
        SET area = ST_Multi(ST_Buffer(
            ST_SetSRID(ST_MakePoint(0.0, -40.0), 4326)::geography, 1000)::geometry)
        WHERE id = $1
        """,
        alert_id,
    )
    results = await validate(db_conn, alert_id)
    rule = next(r for r in results if r.rule_id == "target_count_plausible")
    assert rule.status == "fail"
    assert "below minimum" in (rule.message or "")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_target_count_plausible_passes_with_consented_recipient_in_area(db_conn):
    alert_id = await _insert_alert(db_conn)
    unit_id = await db_conn.fetchval(
        """
        SELECT u.id
        FROM admin_unit u
        JOIN alert a ON a.id = $1
        WHERE ST_Intersects(u.geom, a.area)
        LIMIT 1
        """,
        alert_id,
    )
    if unit_id is None:
        pytest.skip("no admin_unit intersects the fixture alert")
    minimum = await db_conn.fetchval(
        "SELECT value::int FROM app_config WHERE key = 'quality_gate.min_target_count'"
    )
    created: list[int] = []
    for _ in range(max(int(minimum or 1), 1)):
        created.append(
            await db_conn.fetchval(
                """
                INSERT INTO recipient (unit_id, kind, consented_at, consent_source)
                VALUES ($1, 'citizen', now(), 'test_quality_gate')
                RETURNING id
                """,
                unit_id,
            )
        )
    try:
        results = await validate(db_conn, alert_id)
        rule = next(r for r in results if r.rule_id == "target_count_plausible")
        assert rule.status == "pass"
    finally:
        await db_conn.execute("DELETE FROM recipient WHERE id = ANY($1::bigint[])", created)
