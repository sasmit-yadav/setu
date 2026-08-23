"""0017_people_exclude_devices

A village siren is enrolled against a unit exactly like a person is: it is a
recipient row, so the escalation resolver can route to it and the delivery
ladder can hold its evidence. That is the right model — but it made every
count labelled "people" one too many, because v_reachability counted every
recipient row regardless of what was on the other end.

A number the desk calls "people we will warn" must not include a loudspeaker.
The kinds that are devices rather than people live in app_config
(recipient.device_kinds) so adding a second kind of village hardware is a
config change, not another migration.

Deliveries are unaffected: the siren is still targeted, still dispatched, and
still holds its own struck-through assurance rungs. Only the human headcount
changes.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-23
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


VIEW = """
CREATE OR REPLACE VIEW v_reachability AS
WITH cfg AS (
  SELECT
    (SELECT value::int FROM app_config WHERE key='reachability.reached_tier_floor')     AS reached_floor,
    (SELECT value::int FROM app_config WHERE key='reachability.acknowledged_tier_floor') AS ack_floor,
    (SELECT string_to_array(value, ',') FROM app_config WHERE key='recipient.device_kinds')
                                                                                       AS device_kinds
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
CROSS JOIN cfg
LEFT JOIN recipient r
       ON r.unit_id = u.id
      AND r.opted_out_at IS NULL
      AND NOT (r.kind = ANY (COALESCE(cfg.device_kinds, ARRAY[]::text[])))
LEFT JOIN delivery  d ON d.recipient_id = r.id
GROUP BY u.id, u.name, u.level, u.population, cfg.reached_floor, cfg.ack_floor
"""

PRIOR_VIEW = """
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

CONFIG_KEY = "recipient.device_kinds"


def upgrade() -> None:
    # Seeded here rather than only in 04_app_config.sql: the view reads this key
    # and would silently count devices as people on a database whose config had
    # not been refreshed. COALESCE in the view covers a missing row; this makes
    # sure it is not missing.
    op.execute(
        """
        INSERT INTO app_config (key, value, unit, note) VALUES (
          'recipient.device_kinds', 'village_siren', 'csv',
          'Recipient kinds that are village hardware, not people - excluded from '
          'every count the desk labels people, still targeted for delivery'
        )
        ON CONFLICT (key) DO NOTHING
        """
    )
    op.execute(VIEW)


def downgrade() -> None:
    op.execute(PRIOR_VIEW)
    op.execute("DELETE FROM app_config WHERE key = 'recipient.device_kinds'")
