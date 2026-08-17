"""0008_governance

§5.5 + §5.13. app_user, alert_approval (F3 — the UNIQUE(alert_id, approver_id)
is what makes Four-Eyes structural rather than procedural), alert_validation_
result (F1's per-rule results).

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-16
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app_user (
            id            BIGSERIAL PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            role          TEXT NOT NULL,
            unit_scope_id BIGINT REFERENCES admin_unit(id),
            active        BOOLEAN NOT NULL DEFAULT true
        )
    """)

    op.execute("""
        CREATE TABLE alert_approval (
            id          BIGSERIAL PRIMARY KEY,
            alert_id    BIGINT NOT NULL REFERENCES alert(id),
            approver_id BIGINT REFERENCES app_user(id),
            provenance  TEXT NOT NULL,
            decision    TEXT NOT NULL,
            reason      TEXT,
            decided_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (alert_id, approver_id),
            CHECK ((provenance = 'human' AND approver_id IS NOT NULL)
                OR (provenance = 'authoritative_source' AND approver_id IS NULL)),
            CHECK (decision <> 'rejected' OR reason IS NOT NULL)
        )
    """)
    op.execute('CREATE INDEX alert_approval_alert_ix ON alert_approval (alert_id, decision)')

    op.execute("""
        CREATE TABLE alert_validation_result (
            id           BIGSERIAL PRIMARY KEY,
            alert_id     BIGINT NOT NULL REFERENCES alert(id),
            rule_id      TEXT NOT NULL,
            status       TEXT NOT NULL,
            message      TEXT,
            evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX alert_validation_alert_ix
          ON alert_validation_result (alert_id, evaluated_at DESC)
    """)


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS alert_validation_result')
    op.execute('DROP TABLE IF EXISTS alert_approval')
    op.execute('DROP TABLE IF EXISTS app_user')
