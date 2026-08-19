from __future__ import annotations

from typing import Any

import asyncpg

from services.api import config_repo


async def compute_priority(
    conn: asyncpg.Connection,
    *,
    response_severity: str,
    hazard_severity: str,
    vulnerability: float,
    proximity: float,
    wait_minutes: float,
) -> tuple[float, dict[str, Any]]:
    weights = {
        "response_severity": await config_repo.get_float(conn, "assistance.weight.response_severity"),
        "hazard_severity": await config_repo.get_float(conn, "assistance.weight.hazard_severity"),
        "vulnerability": await config_repo.get_float(conn, "assistance.weight.vulnerability"),
        "proximity": await config_repo.get_float(conn, "assistance.weight.proximity"),
        "time_waiting": await config_repo.get_float(conn, "assistance.weight.time_waiting"),
    }
    response_score = float(
        await config_repo.get(
            conn,
            f"assistance.response_severity.{response_severity}",
        )
        or await config_repo.get(conn, "assistance.response_severity.other")
    )
    hazard_score = float(
        await config_repo.get(conn, f"severity.rank.{hazard_severity.lower()}")
    )
    max_wait = float(await config_repo.get(conn, "assistance.max_wait_minutes"))
    wait_ceiling = float(await config_repo.get(conn, "assistance.wait_norm_max"))
    wait_norm = min(wait_minutes / max_wait, wait_ceiling) if max_wait else 0.0
    factors = {
        "response_severity": response_score,
        "hazard_severity": hazard_score,
        "vulnerability": vulnerability,
        "proximity": proximity,
        "time_waiting": wait_norm,
    }
    score = sum(factors[k] * weights[k] for k in weights)
    payload = {
        "weight_version": await config_repo.get(conn, "assistance.weight_version"),
        "weights": weights,
        "factors": factors,
        "score": score,
    }
    return score, payload
