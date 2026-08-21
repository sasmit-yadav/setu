#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.provision_demo_accounts import lookup_unit
from services.api import config_repo
from services.api.db import connect
from services.delivery.assurance import record


async def seed() -> dict[str, int]:
    conn = await connect()
    try:
        named = await config_repo.get(conn, "demo.unit_scope.citizen@setu.example")
        unit_id = await lookup_unit(conn, named) if named else None
        if unit_id is None:
            unit_id = await conn.fetchval(
                "SELECT id FROM admin_unit ORDER BY level DESC, id LIMIT 1"
            )
        if unit_id is None:
            raise SystemExit("admin_unit empty — load geometry before seeding the demo board")
        existing = await conn.fetchval(
            "SELECT id FROM incident WHERE label = 'DEMO-BOARD-001'"
        )
        if existing is not None:
            alert_id = await conn.fetchval(
                "SELECT id FROM alert WHERE incident_id = $1 ORDER BY id LIMIT 1",
                existing,
            )
            delivery_id = await conn.fetchval(
                "SELECT id FROM delivery WHERE alert_id = $1 ORDER BY id LIMIT 1",
                alert_id,
            )
            return {
                "incident_id": int(existing),
                "alert_id": int(alert_id or 0),
                "delivery_id": int(delivery_id or 0),
            }
        incident_id = await conn.fetchval(
            """
            INSERT INTO incident (label, incident_type, status, origin_source)
            VALUES ('DEMO-BOARD-001', 'flood', 'active', 'manual')
            RETURNING id
            """
        )
        checksum = uuid.uuid4().hex
        alert_id = await conn.fetchval(
            """
            INSERT INTO alert (
                source_id, severity, headline, body, lang, area,
                effective_at, expires_at, raw_checksum, incident_id, lifecycle_status
            )
            SELECT 'manual', 'moderate',
                   'Demo flood warning',
                   'Stay away from low-lying roads. This row exists so the Command Board is not empty offline.',
                   'en', geom, now(), now() + interval '6 hours', $1, $2, 'active'
            FROM admin_unit WHERE id = $3
            RETURNING id
            """,
            checksum,
            incident_id,
            unit_id,
        )
        recipient_id = await conn.fetchval(
            """
            INSERT INTO recipient (unit_id, kind, preferred_lang, consented_at)
            VALUES ($1, 'citizen', 'en', now())
            RETURNING id
            """,
            unit_id,
        )
        channel_id = await conn.fetchval("SELECT id FROM channel WHERE code = 'sim'")
        if channel_id is None:
            raise SystemExit("channel table empty — run python run.py seed")
        delivery_id = await conn.fetchval(
            """
            INSERT INTO delivery (alert_id, recipient_id, channel_id, state, simulated)
            VALUES ($1, $2, $3, 'sent', true)
            RETURNING id
            """,
            alert_id,
            recipient_id,
            channel_id,
        )
        await record(
            conn,
            int(delivery_id),
            "provider_accepted",
            source="demo_snapshot",
            evidence_id="demo-board",
        )
        await record(
            conn,
            int(delivery_id),
            "device_delivered",
            source="demo_snapshot",
            evidence_id="demo-board",
        )
        await conn.fetchval(
            """
            INSERT INTO citizen_response (
                delivery_id, alert_id, unit_id, response_type,
                idempotency_key, submitted_at, received_at
            )
            VALUES ($1, $2, $3, 'safe', $4, now(), now())
            RETURNING id
            """,
            delivery_id,
            alert_id,
            unit_id,
            f"demo-board-{uuid.uuid4().hex}",
        )
        return {
            "incident_id": int(incident_id),
            "alert_id": int(alert_id),
            "delivery_id": int(delivery_id),
        }
    finally:
        await conn.close()


def main() -> int:
    result = asyncio.run(seed())
    print(
        f"demo board incident={result['incident_id']} "
        f"alert={result['alert_id']} delivery={result['delivery_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
