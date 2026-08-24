from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from services.api import config_repo
from services.ml.client import translate_text


@dataclass(frozen=True)
class ResolvedText:
    headline: str
    body: str
    lang: str
    source_lang: str
    translated: bool
    fallback_notice: str | None


async def _timeout_s(conn: asyncpg.Connection) -> float:
    return await config_repo.get_float(conn, "ml.http_timeout_s")


async def _ensure_model(conn: asyncpg.Connection) -> int:
    name = await config_repo.get_str(conn, "ml.translate.model_name")
    version = await config_repo.get_str(conn, "ml.translate.model_version")
    artifact = await config_repo.get_str(conn, "ml.translate.hf_id")
    existing = await conn.fetchval(
        "SELECT id FROM model_registry WHERE name = $1 AND version = $2",
        name,
        version,
    )
    if existing is not None:
        return int(existing)
    return int(
        await conn.fetchval(
            """
            INSERT INTO model_registry (
                name, version, artifact_uri, metrics, is_bootstrap, trained_at, active
            )
            VALUES ($1, $2, $3, $4::jsonb, false, now(), true)
            ON CONFLICT (name, version) DO UPDATE SET active = true
            RETURNING id
            """,
            name,
            version,
            artifact,
            '{"backend":"hf_space","class":"measured"}',
        )
    )


async def _case_study_langs(conn: asyncpg.Connection, alert_id: int) -> set[str]:
    rows = await conn.fetch(
        "SELECT key, value FROM app_config WHERE key LIKE 'case_study.bbox.%'"
    )
    langs: set[str] = set()
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
        if not intersects:
            continue
        for severity in ("severe", "extreme"):
            required = await config_repo.get(
                conn, f"quality_gate.required_lang_for_{severity}.{state}"
            )
            if required:
                langs.add(required)
    return langs


async def target_langs_for_alert(conn: asyncpg.Connection, alert_id: int) -> set[str]:
    langs = set(await config_repo.get_csv(conn, "ml.target_langs"))
    langs.update(await _case_study_langs(conn, alert_id))
    preferred = await conn.fetch(
        """
        SELECT DISTINCT r.preferred_lang
        FROM recipient r
        JOIN admin_unit u ON u.id = r.unit_id
        JOIN alert a ON a.id = $1
        WHERE ST_Intersects(u.geom, a.area)
          AND r.consented_at IS NOT NULL
          AND r.opted_out_at IS NULL
        """,
        alert_id,
    )
    for row in preferred:
        if row["preferred_lang"]:
            langs.add(str(row["preferred_lang"]))
    return {lang for lang in langs if lang}


async def _store(
    conn: asyncpg.Connection,
    alert_id: int,
    lang: str,
    headline: str,
    body: str,
    model_id: int | None,
) -> None:
    await conn.execute(
        """
        INSERT INTO alert_translation (alert_id, lang, headline, body, model_id)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (alert_id, lang) DO UPDATE SET
            headline = EXCLUDED.headline,
            body = EXCLUDED.body,
            model_id = EXCLUDED.model_id
        """,
        alert_id,
        lang,
        headline,
        body,
        model_id,
    )


async def _reuse_identical(
    conn: asyncpg.Connection,
    lang: str,
    source_lang: str,
    headline: str,
    body: str,
) -> asyncpg.Record | None:
    """A translation of the same sentence is the same translation.

    alert_translation is keyed per alert, so composing the same wording twice
    used to leave the second alert with an empty cache and a blocked Send even
    though the exact text had already been translated. Look the text up rather
    than the alert id.

    model_id travels with the row. A copy of model output stays attributed to
    that model; a copy of something a human typed stays NULL. The provenance
    belongs to the sentence, not to the alert that happened to carry it first.
    """
    return await conn.fetchrow(
        """
        SELECT t.headline, t.body, t.model_id
        FROM alert_translation t
        JOIN alert a ON a.id = t.alert_id
        WHERE t.lang = $1
          AND a.lang = $2
          AND a.headline = $3
          AND a.body = $4
        ORDER BY t.model_id NULLS LAST, t.alert_id DESC
        LIMIT 1
        """,
        lang,
        source_lang,
        headline,
        body,
    )


async def ensure_translations(conn: asyncpg.Connection, alert_id: int) -> None:
    row = await conn.fetchrow(
        "SELECT headline, body, lang FROM alert WHERE id = $1",
        alert_id,
    )
    if row is None:
        return
    source_lang = str(row["lang"])
    headline = str(row["headline"])
    body = str(row["body"])
    langs: set[str] = {source_lang}
    timeout_s: float | None = None
    try:
        timeout_s = await _timeout_s(conn)
        langs.update(await target_langs_for_alert(conn, alert_id))
    except KeyError:
        pass
    model_id: int | None = None
    for lang in langs:
        exists = await conn.fetchval(
            "SELECT 1 FROM alert_translation WHERE alert_id = $1 AND lang = $2",
            alert_id,
            lang,
        )
        if exists:
            continue
        if lang == source_lang:
            await _store(conn, alert_id, lang, headline, body, None)
            continue
        # Before asking the model: has this exact sentence already been
        # translated for another alert? Composing standard wording twice should
        # not need the model a second time, and must not leave the gate blocked
        # when the model is unreachable.
        reused = await _reuse_identical(conn, lang, source_lang, headline, body)
        if reused is not None:
            await _store(
                conn,
                alert_id,
                lang,
                str(reused["headline"]),
                str(reused["body"]),
                reused["model_id"],
            )
            continue
        if timeout_s is None:
            continue
        model = await config_repo.get_str(conn, "ml.translate.hf_id")
        translated_headline = await translate_text(headline, lang, timeout_s, model)
        translated_body = await translate_text(body, lang, timeout_s, model)
        if not translated_headline or not translated_body:
            continue
        if model_id is None:
            model_id = await _ensure_model(conn)
        await _store(conn, alert_id, lang, translated_headline, translated_body, model_id)


async def fill_open_alert_translations(
    conn: asyncpg.Connection, *, limit: int = 3
) -> int:
    """Translate live drafts the Render API could not reach a model for.

    Hosted compose calls ensure_translations on Render, which cannot see a
    laptop :8001. The quality gate then fails translation_exists and greys
    out Send warning. The laptop worker *can* reach the model — run this
    every idle tick so Malayalam lands in Neon and the desk unlocks.
    """
    rows = await conn.fetch(
        """
        SELECT id FROM alert
        WHERE lifecycle_status IN ('draft', 'active')
          AND severity IN ('severe', 'extreme')
        ORDER BY id DESC
        LIMIT $1
        """,
        limit,
    )
    added = 0
    for row in rows:
        before = await conn.fetchval(
            "SELECT count(*) FROM alert_translation WHERE alert_id = $1",
            row["id"],
        )
        await ensure_translations(conn, int(row["id"]))
        after = await conn.fetchval(
            "SELECT count(*) FROM alert_translation WHERE alert_id = $1",
            row["id"],
        )
        added += max(0, int(after) - int(before or 0))
    return added


async def lang_for_unit(conn: asyncpg.Connection, unit_id: int) -> str | None:
    rows = await conn.fetch(
        "SELECT key, value FROM app_config WHERE key LIKE 'case_study.bbox.%'"
    )
    for row in rows:
        state = str(row["key"]).rsplit(".", 1)[-1]
        south, west, north, east = (float(part) for part in str(row["value"]).split(","))
        intersects = await conn.fetchval(
            """
            SELECT ST_Intersects(
                u.geom,
                ST_MakeEnvelope($1, $2, $3, $4, 4326)
            )
            FROM admin_unit u WHERE u.id = $5
            """,
            west,
            south,
            east,
            north,
            unit_id,
        )
        if not intersects:
            continue
        required = await config_repo.get(conn, f"quality_gate.required_lang_for_severe.{state}")
        if required:
            return required
    return None


async def resolve_alert_text(
    conn: asyncpg.Connection,
    alert_id: int,
    lang: str | None,
) -> ResolvedText:
    row = await conn.fetchrow(
        "SELECT headline, body, lang FROM alert WHERE id = $1",
        alert_id,
    )
    if row is None:
        raise KeyError("alert_not_found")
    source_lang = str(row["lang"])
    headline = str(row["headline"])
    body = str(row["body"])
    notice = await config_repo.get(conn, "translation.fallback_notice")
    wanted = lang or source_lang
    if wanted == source_lang:
        cached_source = await conn.fetchrow(
            """
            SELECT headline, body FROM alert_translation
            WHERE alert_id = $1 AND lang = $2
            """,
            alert_id,
            source_lang,
        )
        if cached_source:
            return ResolvedText(
                headline=str(cached_source["headline"]),
                body=str(cached_source["body"]),
                lang=source_lang,
                source_lang=source_lang,
                translated=False,
                fallback_notice=None,
            )
        return ResolvedText(
            headline=headline,
            body=body,
            lang=source_lang,
            source_lang=source_lang,
            translated=False,
            fallback_notice=None,
        )
    cached = await conn.fetchrow(
        """
        SELECT headline, body FROM alert_translation
        WHERE alert_id = $1 AND lang = $2
        """,
        alert_id,
        wanted,
    )
    if cached:
        return ResolvedText(
            headline=str(cached["headline"]),
            body=str(cached["body"]),
            lang=wanted,
            source_lang=source_lang,
            translated=True,
            fallback_notice=None,
        )
    return ResolvedText(
        headline=headline,
        body=body,
        lang=source_lang,
        source_lang=source_lang,
        translated=False,
        fallback_notice=notice,
    )
