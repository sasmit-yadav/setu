"""0016_reachability_excludes_sim

v_reachability counted simulated carrier ticks as a reached phone. That is
the opposite of the desk copy ("only when the phone actually got it").
Practice sends stay in delivery history; they drop out of reach totals.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-22
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


VIEW = """
CREATE OR REPLACE VIEW v_reachability AS
WITH cfg AS (
  SELECT
    (SELECT value::int FROM app_config WHERE key='reachability.reached_tier_floor')     AS reached_floor,
    (SELECT value::int FROM app_config WHERE key='reachability.acknowledged_tier_floor') AS ack_floor
)
SELECT
    u.id                                   AS unit_id,
    u.name,
    u.level                                AS geometry_level,
    u.population                           AS estimated_population,
    COUNT(DISTINCT r.id)                   AS registered_recipients,
    COUNT(DISTINCT d.recipient_id) FILTER (
        WHERE NOT d.simulated AND assurance_level(d.id) >= cfg.reached_floor)
                                           AS reached_recipients,
    COUNT(DISTINCT d.recipient_id) FILTER (
        WHERE (NOT d.simulated AND assurance_level(d.id) >= cfg.ack_floor)
           OR EXISTS (
                SELECT 1 FROM delivery_event de
                WHERE de.delivery_id = d.id
                  AND de.event_type = 'citizen_response'
           ))
                                           AS acknowledged_recipients,
    COUNT(DISTINCT d.recipient_id) FILTER (
        WHERE d.id IS NOT NULL AND (d.simulated OR assurance_level(d.id) < cfg.reached_floor))
                                           AS unverified_recipients,
    ROUND(100.0 * COUNT(DISTINCT d.recipient_id) FILTER (
        WHERE NOT d.simulated AND assurance_level(d.id) >= cfg.reached_floor)
          / NULLIF(COUNT(DISTINCT r.id), 0), 1)     AS recipient_reach_pct,
    ROUND(100.0 * COUNT(DISTINCT d.recipient_id) FILTER (
        WHERE NOT d.simulated AND assurance_level(d.id) >= cfg.reached_floor)
          / NULLIF(u.population, 0), 1)             AS population_reach_pct,
    MAX(d.queued_at) FILTER (WHERE NOT d.simulated) AS last_dispatch_at
FROM admin_unit u
LEFT JOIN recipient r ON r.unit_id = u.id AND r.opted_out_at IS NULL
LEFT JOIN delivery  d ON d.recipient_id = r.id
CROSS JOIN cfg
GROUP BY u.id, u.name, u.level, u.population, cfg.reached_floor, cfg.ack_floor
"""


def upgrade() -> None:
    op.execute(VIEW)


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW v_reachability AS
        WITH cfg AS (
          SELECT
            (SELECT value::int FROM app_config WHERE key='reachability.reached_tier_floor')     AS reached_floor,
            (SELECT value::int FROM app_config WHERE key='reachability.acknowledged_tier_floor') AS ack_floor
        )
        SELECT
            u.id                                   AS unit_id,
            u.name,
            u.level                                AS geometry_level,
            u.population                           AS estimated_population,
            COUNT(DISTINCT r.id)                   AS registered_recipients,
            COUNT(DISTINCT d.recipient_id) FILTER (WHERE assurance_level(d.id) >= cfg.reached_floor)
                                                   AS reached_recipients,
            COUNT(DISTINCT d.recipient_id) FILTER (WHERE assurance_level(d.id) >= cfg.ack_floor)
                                                   AS acknowledged_recipients,
            COUNT(DISTINCT d.recipient_id) FILTER (WHERE assurance_level(d.id) <  cfg.reached_floor)
                                                   AS unverified_recipients,
            ROUND(100.0 * COUNT(DISTINCT d.recipient_id) FILTER (WHERE assurance_level(d.id) >= cfg.reached_floor)
                  / NULLIF(COUNT(DISTINCT r.id), 0), 1)     AS recipient_reach_pct,
            ROUND(100.0 * COUNT(DISTINCT d.recipient_id) FILTER (WHERE assurance_level(d.id) >= cfg.reached_floor)
                  / NULLIF(u.population, 0), 1)             AS population_reach_pct,
            MAX(d.queued_at)                       AS last_dispatch_at
        FROM admin_unit u
        LEFT JOIN recipient r ON r.unit_id = u.id AND r.opted_out_at IS NULL
        LEFT JOIN delivery  d ON d.recipient_id = r.id
        CROSS JOIN cfg
        GROUP BY u.id, u.name, u.level, u.population, cfg.reached_floor, cfg.ack_floor
        """
    )
