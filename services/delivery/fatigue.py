from __future__ import annotations

from typing import Any

import asyncpg

from services.api import config_repo

TIER_ORDER = (
    ("provider_accept", "provider_accepted"),
    ("device_delivered", "device_delivered"),
    ("opened", "notification_opened"),
    ("acknowledgement", "acknowledged"),
)


async def evaluate(conn: asyncpg.Connection, alert_id: int) -> dict[str, Any]:
    incident_id = await conn.fetchval("SELECT incident_id FROM alert WHERE id = $1", alert_id)
    if incident_id is None:
        return {"incident_id": None, "related_count": 0, "relabel": False}
    window_minutes = await config_repo.get_int(conn, "fatigue.window_minutes")
    count_floor = await config_repo.get_int(conn, "fatigue.alert_count_floor")
    related_count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM alert
        WHERE incident_id = $1
          AND ingested_at >= now() - ($2 * interval '1 minute')
        """,
        incident_id,
        window_minutes,
    )
    never_suppress = await config_repo.get_bool(conn, "fatigue.never_suppress")
    relabel = int(related_count or 0) >= count_floor
    return {
        "incident_id": incident_id,
        "window_minutes": window_minutes,
        "related_count": int(related_count or 0),
        "count_floor": count_floor,
        "relabel": relabel,
        "never_suppress": never_suppress,
    }


async def apply_headline(conn: asyncpg.Connection, alert_id: int, headline: str) -> tuple[str, dict[str, Any]]:
    evaluation = await evaluate(conn, alert_id)
    if not evaluation["relabel"]:
        return headline, evaluation
    prefix = await config_repo.get(conn, "fatigue.relabel_prefix")
    if not prefix or headline.startswith(prefix):
        return headline, evaluation
    return f"{prefix}{headline}", evaluation
