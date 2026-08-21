from __future__ import annotations

import random
from datetime import datetime
from math import asin, cos, radians, sin, sqrt

import asyncpg

from services.api import config_repo
from services.ml.dedup import assign_cluster, next_cluster_id


async def assign_cluster_or_new(conn: asyncpg.Connection, parsed) -> int:
    cluster_id = await assign_cluster(conn, parsed)
    if cluster_id is None:
        return await next_cluster_id(conn)
    return cluster_id


def seconds_apart(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds())


def haversine_m(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
    earth_radius_m: float,
) -> float:
    dlon = radians(lon2 - lon1)
    dlat = radians(lat2 - lat1)
    half = 2
    chord = (
        sin(dlat / half) ** half
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / half) ** half
    )
    return earth_radius_m * half * asin(sqrt(chord))


def spatial_temporal_match(
    *,
    lon1: float,
    lat1: float,
    t1: datetime,
    lon2: float,
    lat2: float,
    t2: datetime,
    radius_m: float,
    window_hours: float,
    earth_radius_m: float,
    seconds_per_hour: float,
) -> bool:
    if seconds_apart(t1, t2) / seconds_per_hour > window_hours:
        return False
    return haversine_m(lon1, lat1, lon2, lat2, earth_radius_m) <= radius_m


def confusion(pairs: list[dict], *, radius_m: float, window_hours: float, earth_radius_m: float, seconds_per_hour: float) -> dict:
    tp = 0
    fp = 0
    tn = 0
    fn = 0
    for pair in pairs:
        a = pair["a"]
        b = pair["b"]
        predicted = spatial_temporal_match(
            lon1=float(a["lon"]),
            lat1=float(a["lat"]),
            t1=datetime.fromisoformat(str(a["t"]).replace("Z", "+00:00")),
            lon2=float(b["lon"]),
            lat2=float(b["lat"]),
            t2=datetime.fromisoformat(str(b["t"]).replace("Z", "+00:00")),
            radius_m=radius_m,
            window_hours=window_hours,
            earth_radius_m=earth_radius_m,
            seconds_per_hour=seconds_per_hour,
        )
        label = bool(pair["label"])
        if predicted and label:
            tp += 1
        elif predicted and not label:
            fp += 1
        elif (not predicted) and (not label):
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        (2 * precision * recall) / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    return {
        "n": len(pairs),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "method": "spatial_temporal",
        "disclosure": (
            "Shipping model is spatial/temporal clustering, not MiniLM. "
            "MiniLM embeddings are used only when the isolated ML service /embed is up."
        ),
    }


async def publish_metrics(conn: asyncpg.Connection, metrics: dict) -> int:
    name = await config_repo.get_str(conn, "dedup.model_name")
    version = await config_repo.get_str(conn, "dedup.model_version")
    existing = await conn.fetchval(
        "SELECT id FROM model_registry WHERE name = $1 AND version = $2",
        name,
        version,
    )
    if existing is not None:
        await conn.execute(
            """
            UPDATE model_registry
            SET metrics = $2::jsonb, trained_at = now(), active = true, is_bootstrap = false
            WHERE id = $1
            """,
            existing,
            metrics,
        )
        return int(existing)
    return int(
        await conn.fetchval(
            """
            INSERT INTO model_registry (
                name, version, artifact_uri, metrics, is_bootstrap, trained_at, active
            )
            VALUES ($1, $2, 'services.ml.dedup', $3::jsonb, false, now(), true)
            ON CONFLICT (name, version) DO UPDATE SET
                metrics = EXCLUDED.metrics,
                trained_at = now(),
                is_bootstrap = false,
                active = true
            RETURNING id
            """,
            name,
            version,
            metrics,
        )
    )


async def evaluate_and_publish(conn: asyncpg.Connection, pairs: list[dict]) -> dict:
    radius_m = await config_repo.get_float(conn, "dedup.spatial_radius_m")
    window_hours = await config_repo.get_float(conn, "dedup.window_hours")
    earth_radius_m = await config_repo.get_float(conn, "geo.earth_radius_m")
    seconds_per_hour = await config_repo.get_float(conn, "time.seconds_per_hour")
    ratio = await config_repo.get_float(conn, "dedup.eval_held_out_ratio")
    ordered = list(pairs)
    random.Random(1).shuffle(ordered)
    start = int(len(ordered) * (1 - ratio))
    held_out = ordered[start:] if start < len(ordered) else ordered
    metrics = confusion(
        held_out,
        radius_m=radius_m,
        window_hours=window_hours,
        earth_radius_m=earth_radius_m,
        seconds_per_hour=seconds_per_hour,
    )
    metrics["held_out_n"] = len(held_out)
    metrics["split_ratio"] = ratio
    metrics["labels"] = "constructed_spatial_temporal_pairs"
    await publish_metrics(conn, metrics)
    return metrics
