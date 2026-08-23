from __future__ import annotations

import json

import asyncpg
from fastapi import APIRouter, Depends, Query

from services.api import config_repo
from services.api.auth import Principal
from services.api.deps import get_conn
from services.api.rbac import OFFICER, require_operational_read
from services.api.schemas import CitizenReplyOut

router = APIRouter(prefix="/api/v1/ops", tags=["ops"])


@router.get("/map")
async def ops_map(
    min_lon: float | None = Query(default=None),
    min_lat: float | None = Query(default=None),
    max_lon: float | None = Query(default=None),
    max_lat: float | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_conn),
    principal: Principal = Depends(require_operational_read),
) -> dict:
    scoped_envelope = False
    if (
        principal.role == OFFICER
        and principal.unit_scope_id is not None
        and min_lon is None
        and min_lat is None
        and max_lon is None
        and max_lat is None
    ):
        envelope = await conn.fetchrow(
            """
            SELECT ST_XMin(geom::geometry) AS min_lon,
                   ST_YMin(geom::geometry) AS min_lat,
                   ST_XMax(geom::geometry) AS max_lon,
                   ST_YMax(geom::geometry) AS max_lat
            FROM admin_unit
            WHERE id = $1
            """,
            principal.unit_scope_id,
        )
        if envelope is not None and envelope["min_lon"] is not None:
            min_lon = float(envelope["min_lon"])
            min_lat = float(envelope["min_lat"])
            max_lon = float(envelope["max_lon"])
            max_lat = float(envelope["max_lat"])
            scoped_envelope = True
    if min_lon is None:
        min_lon = await config_repo.get_float(conn, "map.india_min_lon")
    if min_lat is None:
        min_lat = await config_repo.get_float(conn, "map.india_min_lat")
    if max_lon is None:
        max_lon = await config_repo.get_float(conn, "map.india_max_lon")
    if max_lat is None:
        max_lat = await config_repo.get_float(conn, "map.india_max_lat")
    level = await config_repo.get_int(conn, "map.geometry_level")
    simplify = await config_repo.get_float(conn, "map.simplify_tolerance")
    max_features = await config_repo.get_int(conn, "map.max_features")
    if scoped_envelope:
        finest = await conn.fetchval(
            """
            SELECT MAX(level)
            FROM admin_unit
            WHERE ST_Intersects(geom, ST_MakeEnvelope($1, $2, $3, $4, 4326))
            """,
            min_lon,
            min_lat,
            max_lon,
            max_lat,
        )
        if finest is not None:
            level = int(finest)
            simplify = min(simplify, 0.002)
    tile_source = await config_repo.get_str(conn, "map.tile_source")
    openfreemap = await config_repo.get_str(conn, "map.openfreemap_style_url")
    pmtiles_min_bytes = await config_repo.get_int(conn, "map.pmtiles_min_bytes")
    # Geometry first, WITHOUT joining v_reachability. The join used to be inline
    # here, and it was the whole cost of this endpoint: v_reachability groups
    # over every admin_unit and calls assurance_level() per delivery, so a
    # LEFT JOIN made Postgres aggregate all 8302 units before joining the ~39
    # the bbox actually returned. Measured on Neon: 9.74s joined vs 0.25s for
    # the geometry alone. A qual on unit_id, by contrast, pushes down through
    # the view's GROUP BY, so asking for exactly the units we kept costs 0.66s
    # — same rows, same numbers, ~10x faster end to end.
    #
    # Deliberately NOT a cache. These are the reach figures that move the moment
    # a Send lands, and serving a stale percentage is the one failure this
    # console is built to avoid (Rule 4). Two live queries beat one cached lie.
    units = await conn.fetch(
        """
        SELECT u.id, u.name, u.level,
               ST_AsGeoJSON(ST_Simplify(u.geom::geometry, $6)) AS geom
        FROM admin_unit u
        WHERE u.level = $1
          AND ST_Intersects(u.geom, ST_MakeEnvelope($2, $3, $4, $5, 4326))
          AND (
            $8::bigint IS NULL
            OR ST_Intersects(u.geom, (SELECT geom FROM admin_unit WHERE id = $8))
          )
        ORDER BY u.name
        LIMIT $7
        """,
        level,
        min_lon,
        min_lat,
        max_lon,
        max_lat,
        simplify,
        max_features,
        principal.unit_scope_id if scoped_envelope else None,
    )
    reach_by_unit = {
        int(row["unit_id"]): row
        for row in await conn.fetch(
            """
            SELECT unit_id, recipient_reach_pct, population_reach_pct,
                   registered_recipients, reached_recipients, geometry_level
            FROM v_reachability
            WHERE unit_id = ANY($1::bigint[])
            """,
            [int(row["id"]) for row in units],
        )
    }
    default_zoom = await config_repo.get_float(conn, "map.default_zoom")
    alerts = await conn.fetch(
        """
        SELECT a.id, a.severity, a.headline, a.lifecycle_status,
               ST_AsGeoJSON(
                 ST_Simplify(
                   ST_Buffer(
                     ST_Intersection(a.area::geometry, ST_MakeEnvelope($2, $3, $4, $5, 4326)),
                     0
                   ),
                   $1
                 )
               ) AS geom
        FROM alert a
        WHERE a.lifecycle_status = 'active'
          AND ST_Intersects(a.area, ST_MakeEnvelope($2, $3, $4, $5, 4326))
          AND ST_Contains(ST_MakeEnvelope($2, $3, $4, $5, 4326), ST_Centroid(a.area::geometry))
        ORDER BY a.effective_at DESC
        LIMIT 12
        """,
        simplify,
        min_lon,
        min_lat,
        max_lon,
        max_lat,
    )
    unit_features = []
    for row in units:
        if not row["geom"]:
            continue
        # A unit with no v_reachability row keeps exactly the shape the LEFT JOIN
        # gave it: null percentages and zero counts. Never a fabricated 0%, which
        # would read as "we tried and reached nobody" rather than "nothing known".
        reach = reach_by_unit.get(int(row["id"]))
        recipient_pct = reach["recipient_reach_pct"] if reach else None
        population_pct = reach["population_reach_pct"] if reach else None
        unit_features.append(
            {
                "type": "Feature",
                "geometry": json.loads(row["geom"]),
                "properties": {
                    "unit_id": row["id"],
                    "name": row["name"],
                    "level": row["level"],
                    "geometry_level": reach["geometry_level"] if reach else row["level"],
                    "recipient_reach_pct": float(recipient_pct)
                    if recipient_pct is not None
                    else None,
                    "population_reach_pct": float(population_pct)
                    if population_pct is not None
                    else None,
                    "registered_recipients": (reach["registered_recipients"] if reach else 0) or 0,
                    "reached_recipients": (reach["reached_recipients"] if reach else 0) or 0,
                },
            }
        )
    alert_features = []
    for row in alerts:
        if not row["geom"]:
            continue
        alert_features.append(
            {
                "type": "Feature",
                "geometry": json.loads(row["geom"]),
                "properties": {
                    "alert_id": row["id"],
                    "severity": row["severity"],
                    "headline": row["headline"],
                    "lifecycle_status": row["lifecycle_status"],
                },
            }
        )
    if not unit_features and not alert_features:
        pass
    return {
        "tile_source": tile_source,
        "openfreemap_style_url": openfreemap,
        "pmtiles_min_bytes": pmtiles_min_bytes,
        "center": [(min_lon + max_lon) / 2, (min_lat + max_lat) / 2],
        "zoom": default_zoom,
        "units": {"type": "FeatureCollection", "features": unit_features},
        "alerts": {"type": "FeatureCollection", "features": alert_features},
    }


@router.get("/summary")
async def ops_summary(
    conn: asyncpg.Connection = Depends(get_conn),
    _principal: Principal = Depends(require_operational_read),
) -> dict:
    reach_floor = await config_repo.get_int(conn, "reachability.reached_tier_floor")
    ack_floor = await config_repo.get_int(conn, "reachability.acknowledged_tier_floor")
    row = await conn.fetchrow(
        """
        SELECT
          (SELECT COUNT(*)::int
             FROM delivery d
             JOIN alert a ON a.id = d.alert_id
            WHERE a.lifecycle_status = 'active') AS targeted,
          (SELECT COUNT(*)::int
             FROM delivery d
             JOIN alert a ON a.id = d.alert_id
            WHERE a.lifecycle_status = 'active'
              AND NOT d.simulated
              AND assurance_level(d.id) >= $1) AS delivered,
          (SELECT COUNT(*)::int
             FROM delivery d
             JOIN alert a ON a.id = d.alert_id
            WHERE a.lifecycle_status = 'active'
              AND (
                    (NOT d.simulated AND assurance_level(d.id) >= $2)
                 OR EXISTS (
                      SELECT 1 FROM delivery_event de
                      WHERE de.delivery_id = d.id
                        AND de.event_type = 'citizen_response'
                    )
              )) AS acknowledged,
          (SELECT COUNT(DISTINCT u.id)::int
             FROM admin_unit u
             JOIN alert a ON a.lifecycle_status = 'active'
              AND ST_Intersects(u.geom, a.area)
            WHERE u.level = (
                    SELECT MAX(u2.level)
                    FROM admin_unit u2
                    JOIN alert a2 ON a2.lifecycle_status = 'active'
                     AND ST_Intersects(u2.geom, a2.area)
                  )
              AND NOT EXISTS (
                SELECT 1 FROM relay_node rn WHERE rn.unit_id = u.id AND rn.active
            )) AS at_risk
        """,
        reach_floor,
        ack_floor,
    )
    # A phone the provider accepted is not a person who heard. Anyone reached on
    # a real channel who has still said nothing after the silence window is the
    # Wayanad case: the warning left the office and nobody knows if it landed.
    # Reported per village so the desk can suggest a runner - it never sends one.
    # A database that has not been reseeded must not lose the whole desk to one
    # missing key. Absent means the window is unset, so nothing is reported
    # silent - the feature goes quiet rather than inventing a threshold, and the
    # response keeps its shape so the console does not need to care.
    try:
        silence_minutes = await config_repo.get_int(conn, "relay.silence_minutes")
    except KeyError:
        silence_minutes = 0
    silent = [] if silence_minutes <= 0 else await conn.fetch(
        """
        WITH reached AS (
            SELECT r.unit_id, d.recipient_id, a.id AS alert_id,
                   max(COALESCE(d.sent_at, d.queued_at)) AS last_try
            FROM delivery d
            JOIN channel c ON c.id = d.channel_id
            JOIN recipient r ON r.id = d.recipient_id
            JOIN alert a ON a.id = d.alert_id
            WHERE a.lifecycle_status = 'active'
              AND NOT d.simulated
              AND c.code = ANY (ARRAY['sms', 'ivr', 'fcm', 'email'])
              AND d.state IN ('sent', 'delivered', 'acknowledged')
            GROUP BY r.unit_id, d.recipient_id, a.id
        )
        SELECT reached.unit_id,
               u.name AS unit_name,
               count(*)::int AS silent_people,
               floor(
                 extract(epoch FROM (now() - min(reached.last_try))) / 60
               )::int AS quietest_minutes,
               EXISTS (
                 SELECT 1 FROM delivery hr
                 JOIN channel hc ON hc.id = hr.channel_id
                 JOIN recipient hrr ON hrr.id = hr.recipient_id
                 WHERE hc.code = 'human_relay'
                   AND hrr.unit_id = reached.unit_id
                   AND hr.alert_id = reached.alert_id
               ) AS runner_exists,
               (SELECT count(*)::int FROM relay_node rn
                 WHERE rn.unit_id = reached.unit_id AND rn.active) AS contacts
        FROM reached
        JOIN admin_unit u ON u.id = reached.unit_id
        WHERE NOT EXISTS (
                -- citizen_response keys on the delivery, not the person, so a
                -- reply on any channel counts as this recipient having answered.
                SELECT 1
                FROM citizen_response cr
                JOIN delivery cd ON cd.id = cr.delivery_id
                WHERE cr.alert_id = reached.alert_id
                  AND cd.recipient_id = reached.recipient_id
              )
          AND reached.last_try < now() - make_interval(mins => $1)
        GROUP BY reached.unit_id, u.name, reached.alert_id
        ORDER BY silent_people DESC
        """,
        silence_minutes,
    )
    return {
        "targeted": int(row["targeted"] or 0),
        "delivered": int(row["delivered"] or 0),
        "acknowledged": int(row["acknowledged"] or 0),
        "at_risk": int(row["at_risk"] or 0),
        "delivered_note": "real phones and apps only",
        "acknowledged_note": "someone replied on a real channel",
        # Was "no runner", which reads as "no runner has been sent". It counts
        # villages with nobody registered to send - a preparedness gap.
        "at_risk_note": "village under the live warning with no relay contact registered",
        "silence_minutes": silence_minutes,
        "silent": [
            {
                "unit_id": r["unit_id"],
                "unit_name": r["unit_name"],
                "silent_people": r["silent_people"],
                "quietest_minutes": r["quietest_minutes"],
                "runner_exists": r["runner_exists"],
                "contacts": r["contacts"],
            }
            for r in silent
        ],
    }


@router.get("/replies", response_model=list[CitizenReplyOut])
async def ops_replies(
    conn: asyncpg.Connection = Depends(get_conn),
    _principal: Principal = Depends(require_operational_read),
) -> list[CitizenReplyOut]:
    limit = await config_repo.get_int(conn, "api.list_default_limit")
    rows = await conn.fetch(
        """
        SELECT cr.id, c.code AS channel_code, cr.response_type, cr.free_text,
               u.name AS unit_name, cr.received_at, ac.id AS assistance_case_id,
               a.id AS alert_id, a.headline, a.severity
        FROM citizen_response cr
        JOIN delivery d ON d.id = cr.delivery_id
        JOIN channel c ON c.id = d.channel_id
        JOIN admin_unit u ON u.id = cr.unit_id
        JOIN alert a ON a.id = cr.alert_id
        LEFT JOIN assistance_case ac ON ac.citizen_response_id = cr.id
        WHERE a.lifecycle_status = 'active'
        ORDER BY cr.received_at DESC, cr.id DESC
        LIMIT $1
        """,
        limit,
    )
    return [
        CitizenReplyOut(
            id=int(row["id"]),
            channel_code=str(row["channel_code"]),
            response_type=str(row["response_type"]),
            free_text=row["free_text"],
            unit_name=str(row["unit_name"]),
            received_at=row["received_at"].isoformat(),
            assistance_case_id=int(row["assistance_case_id"]) if row["assistance_case_id"] else None,
            alert_id=int(row["alert_id"]),
            headline=str(row["headline"]),
            severity=str(row["severity"]),
        )
        for row in rows
    ]


@router.get("/feed")
async def ops_feed(
    conn: asyncpg.Connection = Depends(get_conn),
    _principal: Principal = Depends(require_operational_read),
) -> list[dict]:
    limit = await config_repo.get_int(conn, "api.list_default_limit")
    rows = await conn.fetch(
        """
        SELECT de.occurred_at, de.event_type, d.id AS delivery_id,
               a.id AS alert_id, a.headline, a.severity, c.code AS channel_code,
               d.simulated, cr.response_type, cr.free_text
        FROM delivery_event de
        JOIN delivery d ON d.id = de.delivery_id
        JOIN alert a ON a.id = d.alert_id
        JOIN channel c ON c.id = d.channel_id
        LEFT JOIN LATERAL (
            SELECT response_type, free_text
            FROM citizen_response
            WHERE delivery_id = d.id
            ORDER BY received_at DESC, id DESC
            LIMIT 1
        ) cr ON de.event_type = 'citizen_response'
        WHERE de.event_type IN (
            'acknowledged', 'device_delivered', 'citizen_response', 'notification_opened'
        )
        ORDER BY de.occurred_at DESC, de.id DESC
        LIMIT $1
        """,
        limit,
    )
    return [
        {
            "occurred_at": row["occurred_at"].isoformat(),
            "event_type": row["event_type"],
            "delivery_id": row["delivery_id"],
            "alert_id": row["alert_id"],
            "headline": row["headline"],
            "severity": row["severity"],
            "channel_code": row["channel_code"],
            "simulated": bool(row["simulated"]),
            "response_type": row["response_type"],
            "free_text": row["free_text"],
        }
        for row in rows
    ]
