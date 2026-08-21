from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.ingestion.types import ParsedAlert
from services.ml.dedup import assign_cluster, cosine


def test_cosine_of_identical_vectors_is_one():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_of_orthogonal_vectors_is_zero():
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_embed_veto_uses_config_threshold(db_conn, delivery_row, monkeypatch):
    alert_id = delivery_row["alert_id"]
    await db_conn.execute("UPDATE alert SET cluster_id = id WHERE id = $1", alert_id)
    loc = await db_conn.fetchrow(
        """
        SELECT ST_X(ST_Centroid(area::geometry)) AS lon,
               ST_Y(ST_Centroid(area::geometry)) AS lat,
               source_id, effective_at, headline
        FROM alert WHERE id = $1
        """,
        alert_id,
    )
    assert loc is not None

    async def fake_embed(texts: list[str], timeout_s: float, model: str) -> list[list[float]]:
        assert model
        assert len(texts) == 2
        return [[1.0, 0.0], [0.0, 1.0]]

    monkeypatch.setattr("services.ml.dedup.embed_texts", fake_embed)
    parsed = ParsedAlert(
        external_id="t1",
        source_id=str(loc["source_id"]),
        severity="moderate",
        headline="Unrelated wording",
        body="Body",
        lang="en",
        lon=float(loc["lon"]),
        lat=float(loc["lat"]),
        effective_at=loc["effective_at"].replace(tzinfo=UTC)
        if loc["effective_at"].tzinfo is None
        else loc["effective_at"],
        expires_at=datetime.now(UTC),
        estimated_onset_at=None,
        raw_checksum="x",
        etag=None,
    )
    clustered = await assign_cluster(db_conn, parsed)
    assert clustered is None
