from __future__ import annotations

import json
from pathlib import Path

from services.ingestion.adapters.gdacs import GdacsAdapter

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_gdacs_identifier_stable():
    feature = json.loads((FIXTURES / "gdacs_search.json").read_text(encoding="utf-8"))["features"][0]
    props = feature["properties"]
    ident = GdacsAdapter.make_identifier(props)
    assert ident == f"{props['eventtype']}:{props['eventid']}:{props['episodeid']}"


def test_gdacs_india_bbox_filter():
    adapter = GdacsAdapter(
        "https://example.test/search",
        {"minlatitude": 6, "maxlatitude": 38, "minlongitude": 68, "maxlongitude": 98},
        30,
        304,
    )
    india_feature = {
        "geometry": {"coordinates": [76.1, 11.6]},
        "properties": {"affectedcountries": [{"iso3": "IND"}]},
    }
    assert adapter._in_india(india_feature) is True
    assert adapter._in_india({"geometry": {"coordinates": [2.0, 48.0]}, "properties": {}}) is False
