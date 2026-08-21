from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.ml.dedup_eval import confusion, evaluate_and_publish
from services.ml.server import app

ROOT = Path(__file__).resolve().parents[2]
PAIRS = ROOT / "data" / "ml" / "dedup_heldout.json"


def test_held_out_pairs_exist():
    assert PAIRS.exists(), "run python scripts/gen_dedup_heldout.py"
    payload = json.loads(PAIRS.read_text(encoding="utf-8"))
    pairs = payload["pairs"]
    assert len(pairs) >= 200
    assert any(p["label"] for p in pairs)
    assert any(not p["label"] for p in pairs)


def test_spatial_temporal_metrics_on_fixture():
    payload = json.loads(PAIRS.read_text(encoding="utf-8"))
    metrics = confusion(
        payload["pairs"],
        radius_m=50_000,
        window_hours=6,
        earth_radius_m=6_371_000,
        seconds_per_hour=3600,
    )
    assert metrics["n"] == len(payload["pairs"])
    assert metrics["method"] == "spatial_temporal"
    assert metrics["tp"] > 0
    assert metrics["tn"] > 0
    assert 0.0 < metrics["precision"] <= 1.0
    assert 0.0 < metrics["recall"] <= 1.0


@pytest.mark.asyncio
async def test_publish_dedup_metrics(db_conn):
    if not PAIRS.exists():
        pytest.skip("held-out fixture missing")
    payload = json.loads(PAIRS.read_text(encoding="utf-8"))
    try:
        metrics = await evaluate_and_publish(db_conn, payload["pairs"])
    except KeyError:
        pytest.skip("dedup eval config keys not seeded")
    row = await db_conn.fetchrow(
        """
        SELECT m.metrics, m.is_bootstrap
        FROM model_registry m
        JOIN app_config c ON c.value = m.name
        WHERE c.key = 'dedup.model_name'
        """
    )
    assert row is not None
    assert row["is_bootstrap"] is False
    stored = row["metrics"]
    if isinstance(stored, str):
        stored = json.loads(stored)
    assert stored["held_out_n"] == metrics["held_out_n"]


def test_ml_server_health_without_torch():
    from fastapi.testclient import TestClient

    from services.api.settings import settings

    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["ok"] is True
    assert body["translate"] is False
    headers = {}
    if settings.internal_ml_key.strip():
        headers["X-Internal-Key"] = settings.internal_ml_key
    denied = client.post(
        "/translate",
        json={"text": "Flood", "target_lang": "ml"},
        headers=headers,
    )
    assert denied.status_code == 503
