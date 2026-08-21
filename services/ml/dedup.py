from __future__ import annotations

from datetime import timedelta
from math import sqrt

import asyncpg

from services.api import config_repo
from services.ingestion.types import ParsedAlert
from services.ml.client import embed_texts


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_left = sqrt(sum(a * a for a in left))
    norm_right = sqrt(sum(b * b for b in right))
    if norm_left <= 0.0 or norm_right <= 0.0:
        return 0.0
    return dot / (norm_left * norm_right)


async def assign_cluster(conn: asyncpg.Connection, parsed: ParsedAlert) -> int | None:
    window_hours = await config_repo.get_float(conn, "dedup.window_hours")
    seconds_per_hour = await config_repo.get_float(conn, "time.seconds_per_hour")
    row = await conn.fetchrow(
        """
        SELECT cluster_id, id, headline
        FROM alert
        WHERE source_id = $1
          AND cluster_id IS NOT NULL
          AND lifecycle_status IN ('draft', 'active', 'superseded')
          AND ABS(EXTRACT(EPOCH FROM (effective_at - $2::timestamptz))) / $7 <= $3
          AND ST_DWithin(
                area::geography,
                ST_SetSRID(ST_MakePoint($4, $5), 4326)::geography,
                $6
              )
        ORDER BY effective_at DESC
        LIMIT 1
        """,
        parsed.source_id,
        parsed.effective_at,
        window_hours,
        parsed.lon,
        parsed.lat,
        await config_repo.get_float(conn, "dedup.spatial_radius_m"),
        seconds_per_hour,
    )
    if row is None:
        return None
    cluster_id = int(row["cluster_id"]) if row["cluster_id"] is not None else int(row["id"])
    timeout_s = await config_repo.get_float(conn, "ml.http_timeout_s")
    threshold = await config_repo.get_float(conn, "dedup.similarity_threshold")
    model = await config_repo.get_str(conn, "ml.embed.hf_id")
    vectors = await embed_texts(
        [parsed.headline, str(row["headline"])],
        timeout_s,
        model=model,
    )
    if vectors is None:
        return cluster_id
    if cosine(vectors[0], vectors[1]) < threshold:
        return None
    return cluster_id


async def next_cluster_id(conn: asyncpg.Connection) -> int:
    value = await conn.fetchval("SELECT COALESCE(MAX(cluster_id), 0) + 1 FROM alert")
    return int(value)


def window_bound(hours: float) -> timedelta:
    return timedelta(hours=hours)
