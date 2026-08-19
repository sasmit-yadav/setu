from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from services.ingestion.normalize import parse_usgs
from services.ingestion.types import RawAlert

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parse_usgs_feature(db_conn):
    feature = json.loads((FIXTURES / "usgs_feature.json").read_text(encoding="utf-8"))
    body = json.dumps(feature, sort_keys=True).encode()
    raw = RawAlert(
        body=body,
        etag=None,
        fetched_at=datetime.now(UTC),
        checksum=hashlib.sha256(body).hexdigest(),
    )
    parsed = await parse_usgs(db_conn, raw)
    assert parsed.source_id == "usgs"
    assert parsed.external_id == feature["id"]
    assert parsed.estimated_onset_at is None
    assert parsed.severity in {"minor", "moderate", "severe", "extreme"}
