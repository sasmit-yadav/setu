"""0006_audit_and_reach_prediction

Base spec §5.10 + §5.11 (v2.1, unchanged). The hash-chained, append-only audit
ledger and its immutability trigger, plus reach_prediction. This is the last
migration of the base spec — 0007 onward is the v3.0 operational-closure layer,
and Part 13's property test `test_assurance_events_never_produce_illegal_states`
and the Day-4 exit gate's round-trip check (`upgrade head -> downgrade 0006 ->
upgrade head`) both anchor on this revision being the pre-v3.0 boundary.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-16
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE audit_event (
            id          BIGSERIAL PRIMARY KEY,
            alert_id    BIGINT REFERENCES alert(id),
            delivery_id BIGINT REFERENCES delivery(id),
            event_type  TEXT NOT NULL,
            payload     JSONB NOT NULL,
            actor       TEXT,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            prev_hash   TEXT NOT NULL,
            hash        TEXT NOT NULL
        )
    """)
    op.execute('CREATE UNIQUE INDEX audit_hash_uix ON audit_event (hash)')

    op.execute("""
        CREATE OR REPLACE FUNCTION audit_no_mutate() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'audit_event is append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER audit_immutable
          BEFORE UPDATE OR DELETE ON audit_event
          FOR EACH ROW EXECUTE FUNCTION audit_no_mutate()
    """)

    op.execute("""
        CREATE TABLE reach_prediction (
            alert_id   BIGINT NOT NULL REFERENCES alert(id),
            unit_id    BIGINT NOT NULL REFERENCES admin_unit(id),
            risk_score NUMERIC NOT NULL CHECK (risk_score BETWEEN 0 AND 1),
            model_id   SMALLINT NOT NULL REFERENCES model_registry(id),
            features   JSONB NOT NULL,
            PRIMARY KEY (alert_id, unit_id)
        )
    """)


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS reach_prediction')
    op.execute('DROP TRIGGER IF EXISTS audit_immutable ON audit_event')
    op.execute('DROP FUNCTION IF EXISTS audit_no_mutate()')
    op.execute('DROP TABLE IF EXISTS audit_event')
