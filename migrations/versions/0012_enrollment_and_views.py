"""0012_enrollment_and_views

§5.6's v3.0 columns + §5.12 + §5.13. recipient.phone_hash (Trap 11's fix —
pgp_sym_encrypt is randomized, so UNIQUE(phone_enc) never fires; phone_hash is
a deterministic HMAC-with-pepper instead) + consent_source + opted_out_at,
backfilled; the three derived views (D7f reachability, D8f vulnerability,
D13f lead-time + its own coverage view).

§5.13's warning, honoured here: this migration FAILS LOUDLY if
PHONE_HASH_PEPPER is absent — it does not fall back to writing NULLs, which
would leave the unique index inert and silently re-introduce Trap 11.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-16
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Sequence, Union

from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pepper = os.environ.get("PHONE_HASH_PEPPER", "")
    if not pepper:
        raise RuntimeError(
            "PHONE_HASH_PEPPER is not set. This migration refuses to proceed: "
            "backfilling phone_hash as NULL would leave the unique index inert "
            "and silently re-introduce Trap 11 (§5.13's stated failure mode). "
            "Run `python scripts/gen_secrets.py`, put the value in .env, then retry."
        )

    op.execute('ALTER TABLE recipient ADD COLUMN phone_hash BYTEA')
    op.execute("ALTER TABLE recipient ADD COLUMN consent_source TEXT")
    op.execute('ALTER TABLE recipient ADD COLUMN opted_out_at TIMESTAMPTZ')

    # Backfill any pre-existing rows deterministically, in Python (not pgcrypto's
    # hmac, to keep the pepper out of SQL text / logs). Empty on a fresh db.
    conn = op.get_bind()
    rows = conn.exec_driver_sql(
        "SELECT id, phone_enc FROM recipient WHERE phone_enc IS NOT NULL AND phone_hash IS NULL"
    ).fetchall()
    for row_id, phone_enc in rows:
        # phone_enc is pgp_sym_encrypt ciphertext; the plaintext isn't available
        # without the symmetric key here, so the backfill re-derives phone_hash
        # from the DECRYPTED number via a server-side round trip per row.
        decrypted = conn.exec_driver_sql(
            "SELECT pgp_sym_decrypt(phone_enc, :key) FROM recipient WHERE id = :id",
            {"key": os.environ.get("PGCRYPTO_SYM_KEY", ""), "id": row_id},
        ).scalar()
        if decrypted is None:
            continue
        digest = hmac.new(pepper.encode(), decrypted.encode(), hashlib.sha256).digest()
        conn.exec_driver_sql(
            "UPDATE recipient SET phone_hash = :h WHERE id = :id",
            {"h": digest, "id": row_id},
        )

    op.execute("""
        CREATE UNIQUE INDEX recipient_phone_hash_uix
          ON recipient (phone_hash) WHERE phone_hash IS NOT NULL
    """)

    # ═══ D7f REACHABILITY ═══ two denominators, geometry_level labelled (§4.1).
    op.execute("""
        CREATE VIEW v_reachability AS
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
    """)

    # ═══ D8f COMMUNICATION VULNERABILITY ═══ degrades honestly if OpenCelliD slipped.
    op.execute("""
        CREATE VIEW v_communication_vulnerability AS
        WITH cfg AS (
          SELECT
            (SELECT value::numeric FROM app_config WHERE key='vuln.tower_count_floor')      AS tower_floor,
            (SELECT value::numeric FROM app_config WHERE key='vuln.terrain_ruggedness_ceiling') AS terrain_ceil,
            (SELECT value::numeric FROM app_config WHERE key='vuln.historical_reach_floor_pct') AS reach_floor
        )
        SELECT
            u.id AS unit_id, u.name,
            uf.tower_count_5km, uf.nearest_tower_km, uf.terrain_ruggedness,
            rv.recipient_reach_pct AS historical_reach_pct,
            ARRAY_REMOVE(ARRAY[
              CASE WHEN uf.tower_count_5km IS NOT NULL AND uf.tower_count_5km < cfg.tower_floor
                   THEN 'low_tower_density' END,
              CASE WHEN uf.terrain_ruggedness IS NOT NULL AND uf.terrain_ruggedness > cfg.terrain_ceil
                   THEN 'terrain_obstruction' END,
              CASE WHEN rv.recipient_reach_pct IS NOT NULL AND rv.recipient_reach_pct < cfg.reach_floor
                   THEN 'historical_delivery_failure' END,
              CASE WHEN NOT EXISTS (SELECT 1 FROM relay_node rn WHERE rn.unit_id = u.id AND rn.active)
                   THEN 'no_relay_coverage' END
            ], NULL) AS primary_factors,
            CASE
              WHEN uf.tower_count_5km IS NULL THEN 'unknown_connectivity_features_pending'
              WHEN uf.tower_count_5km < cfg.tower_floor AND uf.terrain_ruggedness > cfg.terrain_ceil
                   THEN 'ivr_plus_field_relay'
              WHEN uf.tower_count_5km < cfg.tower_floor THEN 'sms_plus_ivr'
              ELSE 'standard'
            END AS recommended_fallback
        FROM admin_unit u
        JOIN unit_features uf ON uf.unit_id = u.id
        LEFT JOIN v_reachability rv ON rv.unit_id = u.id
        CROSS JOIN cfg
    """)

    # ═══ D13f WARNING LEAD TIME ═══ only where a forecast onset genuinely exists.
    op.execute("""
        CREATE VIEW v_lead_time AS
        SELECT
            a.id AS alert_id, a.incident_id, d.recipient_id,
            r.unit_id,
            EXTRACT(EPOCH FROM (a.estimated_onset_at - de.occurred_at))/60 AS lead_time_minutes
        FROM alert a
        JOIN delivery d ON d.alert_id = a.id
        JOIN recipient r ON r.id = d.recipient_id
        JOIN delivery_event de ON de.delivery_id = d.id AND de.event_type = 'device_delivered'
        WHERE a.estimated_onset_at IS NOT NULL
    """)

    op.execute("""
        CREATE VIEW v_lead_time_coverage AS
        SELECT
            COUNT(*) FILTER (WHERE estimated_onset_at IS NOT NULL) AS alerts_with_onset,
            COUNT(*)                                               AS alerts_total,
            ROUND(100.0 * COUNT(*) FILTER (WHERE estimated_onset_at IS NOT NULL)
                  / NULLIF(COUNT(*), 0), 1)                        AS coverage_pct
        FROM alert WHERE lifecycle_status IN ('active','superseded','resolved')
    """)


def downgrade() -> None:
    op.execute('DROP VIEW IF EXISTS v_lead_time_coverage')
    op.execute('DROP VIEW IF EXISTS v_lead_time')
    op.execute('DROP VIEW IF EXISTS v_communication_vulnerability')
    op.execute('DROP VIEW IF EXISTS v_reachability')
    op.execute('DROP INDEX IF EXISTS recipient_phone_hash_uix')
    op.execute('ALTER TABLE recipient DROP COLUMN IF EXISTS opted_out_at')
    op.execute('ALTER TABLE recipient DROP COLUMN IF EXISTS consent_source')
    op.execute('ALTER TABLE recipient DROP COLUMN IF EXISTS phone_hash')
