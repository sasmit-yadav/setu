from __future__ import annotations

import json
from typing import Any

import asyncpg

from services.api import config_repo


async def ensure_bootstrap_model(conn: asyncpg.Connection) -> int:
    name = await config_repo.get_str(conn, "reach_risk.model_name")
    version = await config_repo.get_str(conn, "reach_risk.model_version")
    existing = await conn.fetchval(
        "SELECT id FROM model_registry WHERE name = $1 AND version = $2",
        name,
        version,
    )
    if existing is not None:
        return int(existing)
    return int(
        await conn.fetchval(
            """
            INSERT INTO model_registry (
                name, version, artifact_uri, metrics, is_bootstrap, trained_at, active
            )
            VALUES ($1, $2, 'services.ml.reach_risk', $3::jsonb, true, now(), true)
            ON CONFLICT (name, version) DO UPDATE SET active = true
            RETURNING id
            """,
            name,
            version,
            '{"class":"ours_seeded","disclosure":"Weighted structural formula. Not a trained acknowledgement model."}',
        )
    )


def _score(features: dict[str, float], weights: dict[str, float]) -> float:
    total = 0.0
    weight_sum = 0.0
    for key, weight in weights.items():
        total += weight * features.get(key, 0.0)
        weight_sum += weight
    if weight_sum <= 0.0:
        return 0.0
    raw = total / weight_sum
    return min(max(raw, 0.0), 1.0)


async def predict_for_alert(conn: asyncpg.Connection, alert_id: int) -> int:
    model_id = await ensure_bootstrap_model(conn)
    tower_floor = await config_repo.get_float(conn, "vuln.tower_count_floor")
    terrain_ceil = await config_repo.get_float(conn, "vuln.terrain_ruggedness_ceiling")
    w_tower = await config_repo.get_float(conn, "reach_risk.weight.tower_gap")
    w_terrain = await config_repo.get_float(conn, "reach_risk.weight.terrain")
    w_elevation = await config_repo.get_float(conn, "reach_risk.weight.elevation")
    elevation_scale = await config_repo.get_float(conn, "reach_risk.elevation_scale_m")
    rows = await conn.fetch(
        """
        SELECT u.id AS unit_id, uf.tower_count_5km, uf.terrain_ruggedness,
               uf.mean_elevation_m, uf.nearest_tower_km
        FROM admin_unit u
        JOIN alert a ON a.id = $1
        LEFT JOIN unit_features uf ON uf.unit_id = u.id
        WHERE ST_Intersects(u.geom, a.area)
        """,
        alert_id,
    )
    written = 0
    weights = {
        "tower_gap": w_tower,
        "terrain": w_terrain,
        "elevation": w_elevation,
    }
    for row in rows:
        towers = float(row["tower_count_5km"] or 0)
        terrain = float(row["terrain_ruggedness"] or 0)
        elevation = float(row["mean_elevation_m"] or 0)
        features: dict[str, Any] = {
            "tower_count_5km": towers,
            "terrain_ruggedness": terrain,
            "mean_elevation_m": elevation,
            "nearest_tower_km": float(row["nearest_tower_km"] or 0),
            "tower_gap": min(max((tower_floor - towers) / tower_floor, 0.0), 1.0) if tower_floor else 0.0,
            "terrain": min(max(terrain / terrain_ceil, 0.0), 1.0) if terrain_ceil else 0.0,
            "elevation": min(max(elevation / elevation_scale, 0.0), 1.0) if elevation_scale else 0.0,
        }
        score = _score(
            {k: float(features[k]) for k in ("tower_gap", "terrain", "elevation")},
            weights,
        )
        await conn.execute(
            """
            INSERT INTO reach_prediction (alert_id, unit_id, risk_score, model_id, features)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            ON CONFLICT (alert_id, unit_id) DO UPDATE SET
                risk_score = EXCLUDED.risk_score,
                model_id = EXCLUDED.model_id,
                features = EXCLUDED.features
            """,
            alert_id,
            row["unit_id"],
            score,
            model_id,
            json.dumps(features),
        )
        written += 1
    return written


async def validate_case_study(conn: asyncpg.Connection) -> dict:
    model_id = await ensure_bootstrap_model(conn)
    names = await config_repo.get_csv(conn, "reach_risk.case_study_unit_names")
    flagged = 0
    found: list[dict[str, Any]] = []
    floor = await config_repo.get_float(conn, "reach_risk.case_study_flag_floor")
    for name in names:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.name, uf.tower_count_5km, uf.terrain_ruggedness,
                   uf.mean_elevation_m, uf.nearest_tower_km
            FROM admin_unit u
            LEFT JOIN unit_features uf ON uf.unit_id = u.id
            WHERE u.name ILIKE $1
            ORDER BY u.level DESC, u.id
            LIMIT 1
            """,
            f"%{name}%",
        )
        if row is None:
            found.append({"name": name, "present": False, "flagged": False})
            continue
        tower_floor = await config_repo.get_float(conn, "vuln.tower_count_floor")
        terrain_ceil = await config_repo.get_float(conn, "vuln.terrain_ruggedness_ceiling")
        w_tower = await config_repo.get_float(conn, "reach_risk.weight.tower_gap")
        w_terrain = await config_repo.get_float(conn, "reach_risk.weight.terrain")
        w_elevation = await config_repo.get_float(conn, "reach_risk.weight.elevation")
        elevation_scale = await config_repo.get_float(conn, "reach_risk.elevation_scale_m")
        towers = float(row["tower_count_5km"] or 0)
        terrain = float(row["terrain_ruggedness"] or 0)
        elevation = float(row["mean_elevation_m"] or 0)
        features = {
            "tower_gap": min(max((tower_floor - towers) / tower_floor, 0.0), 1.0) if tower_floor else 0.0,
            "terrain": min(max(terrain / terrain_ceil, 0.0), 1.0) if terrain_ceil else 0.0,
            "elevation": min(max(elevation / elevation_scale, 0.0), 1.0) if elevation_scale else 0.0,
        }
        score = _score(features, {"tower_gap": w_tower, "terrain": w_terrain, "elevation": w_elevation})
        is_flagged = score >= floor
        if is_flagged:
            flagged += 1
        found.append(
            {
                "name": name,
                "unit_id": int(row["id"]),
                "unit_name": row["name"],
                "present": True,
                "risk_score": score,
                "flagged": is_flagged,
                "model_id": model_id,
            }
        )
    metrics = {
        "n": len(names),
        "present": sum(1 for item in found if item["present"]),
        "flagged": flagged,
        "units": found,
        "disclosure": (
            "Bootstrap model. Validated as a case study against named units "
            "(n equals the configured name list). This is not a trained acknowledgement model."
        ),
    }
    await conn.execute(
        """
        INSERT INTO model_registry (
            name, version, artifact_uri, metrics, is_bootstrap, trained_at, active
        )
        VALUES ($1, $2, 'services.ml.reach_risk', $3::jsonb, true, now(), true)
        ON CONFLICT (name, version) DO UPDATE SET
            metrics = EXCLUDED.metrics,
            trained_at = now(),
            active = true
        """,
        await config_repo.get_str(conn, "reach_risk.case_study_name"),
        await config_repo.get_str(conn, "reach_risk.case_study_version"),
        json.dumps(metrics),
    )
    return metrics

