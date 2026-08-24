from __future__ import annotations

import pytest

from services.ml.translate import (
    ensure_translations,
    fill_open_alert_translations,
    resolve_alert_text,
)


@pytest.mark.asyncio
async def test_resolve_falls_back_with_notice(db_conn, delivery_row):
    alert_id = delivery_row["alert_id"]
    resolved = await resolve_alert_text(db_conn, alert_id, "ml")
    assert resolved.translated is False
    assert resolved.lang == "en"
    notice = await db_conn.fetchval(
        "SELECT value FROM app_config WHERE key = 'translation.fallback_notice'"
    )
    if notice:
        assert resolved.fallback_notice == notice


@pytest.mark.asyncio
async def test_ensure_translations_caches_ml_output(db_conn, delivery_row, monkeypatch):
    alert_id = delivery_row["alert_id"]

    async def fake_translate(text: str, target_lang: str, timeout_s: float, model: str = "") -> str:
        return f"{target_lang}:{text}"

    monkeypatch.setattr("services.ml.client.translate_text", fake_translate)
    monkeypatch.setattr("services.ml.translate.translate_text", fake_translate)
    await db_conn.execute(
        """
        INSERT INTO app_config (key, value, unit, note) VALUES
          ('ml.http_timeout_s', '8', 'seconds', 'test'),
          ('ml.target_langs', 'ml', 'csv', 'test')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """
    )
    await ensure_translations(db_conn, alert_id)
    row = await db_conn.fetchrow(
        "SELECT headline, body FROM alert_translation WHERE alert_id = $1 AND lang = 'ml'",
        alert_id,
    )
    assert row is not None
    assert str(row["headline"]).startswith("ml:")
    resolved = await resolve_alert_text(db_conn, alert_id, "ml")
    assert resolved.translated is True
    assert resolved.fallback_notice is None


@pytest.mark.asyncio
async def test_fill_open_alert_translations_uses_worker_path(
    db_conn, delivery_row, monkeypatch
):
    alert_id = delivery_row["alert_id"]
    await db_conn.execute(
        "UPDATE alert SET severity = 'extreme', lifecycle_status = 'draft' WHERE id = $1",
        alert_id,
    )
    await db_conn.execute(
        "DELETE FROM alert_translation WHERE alert_id = $1 AND lang = 'ml'",
        alert_id,
    )

    async def fake_translate(text: str, target_lang: str, timeout_s: float, model: str = "") -> str:
        return f"{target_lang}:{text}"

    monkeypatch.setattr("services.ml.translate.translate_text", fake_translate)
    await db_conn.execute(
        """
        INSERT INTO app_config (key, value, unit, note) VALUES
          ('ml.http_timeout_s', '8', 'seconds', 'test'),
          ('ml.target_langs', 'ml', 'csv', 'test')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """
    )
    added = await fill_open_alert_translations(db_conn, limit=5)
    assert added >= 1
    row = await db_conn.fetchrow(
        "SELECT headline FROM alert_translation WHERE alert_id = $1 AND lang = 'ml'",
        alert_id,
    )
    assert row is not None
    assert str(row["headline"]).startswith("ml:")
