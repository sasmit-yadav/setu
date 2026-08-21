from __future__ import annotations

import re

import pytest

from services.api import config_repo
from services.api.routers.webhooks import _build_ivr_twiml

DIGITS = re.compile(r"\d+")


@pytest.mark.asyncio
async def test_twiml_digits_come_from_config(db_conn, delivery_row):
    response = await _build_ivr_twiml(int(delivery_row["id"]), "/cb", db_conn, mode="")
    xml = response.body.decode() if isinstance(response.body, (bytes, bytearray)) else str(response.body)
    xml = re.sub(r"<\?xml[^?]*\?>", "", xml)
    allowed = {
        await config_repo.get_str(db_conn, "ivr.gather_digits"),
        await config_repo.get_str(db_conn, "ivr.gather_timeout_s"),
        await config_repo.get_str(db_conn, "ivr.dtmf.safe"),
        await config_repo.get_str(db_conn, "ivr.dtmf.need_help"),
        str(delivery_row["id"]),
        str(delivery_row["alert_id"]),
    }
    scrubbed = xml
    for token in sorted(allowed, key=len, reverse=True):
        if token:
            scrubbed = scrubbed.replace(token, "")
    leftover = DIGITS.findall(scrubbed)
    assert leftover == [], leftover
