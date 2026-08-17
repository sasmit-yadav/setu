"""0002_config_and_sources

Base spec §5.2 (v2.1 + the is_authoritative column Rule 12 needs, added here
rather than bolted on later since nothing depends on it being absent first).
app_config + alert_source + channel + escalation_policy.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-16
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app_config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            unit  TEXT,
            note  TEXT
        )
    """)

    op.execute("""
        CREATE TABLE alert_source (
            source_id        TEXT PRIMARY KEY,
            class_path       TEXT NOT NULL,
            config           JSONB NOT NULL,
            poll_interval_s  INTEGER NOT NULL,
            is_authoritative BOOLEAN NOT NULL DEFAULT false,
            enabled          BOOLEAN NOT NULL DEFAULT true
        )
    """)

    op.execute("""
        CREATE TABLE channel (
            id          SMALLSERIAL PRIMARY KEY,
            code        TEXT UNIQUE NOT NULL,
            class_path  TEXT NOT NULL,
            config      JSONB NOT NULL,
            cost_weight NUMERIC NOT NULL DEFAULT 0,
            enabled     BOOLEAN NOT NULL DEFAULT true
        )
    """)

    op.execute("""
        CREATE TABLE escalation_policy (
            id                        SMALLSERIAL PRIMARY KEY,
            severity                  TEXT NOT NULL,
            step_order                SMALLINT NOT NULL,
            channel_id                SMALLINT NOT NULL REFERENCES channel(id),
            wait_before_next_s        INTEGER NOT NULL,
            backoff_multiplier        NUMERIC NOT NULL DEFAULT 1.0,
            jitter_ms                 INTEGER NOT NULL DEFAULT 0,
            max_wait_s                INTEGER,
            max_attempts              SMALLINT NOT NULL,
            applies_if_reach_risk_gte NUMERIC,
            UNIQUE (severity, step_order)
        )
    """)


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS escalation_policy')
    op.execute('DROP TABLE IF EXISTS channel')
    op.execute('DROP TABLE IF EXISTS alert_source')
    op.execute('DROP TABLE IF EXISTS app_config')
