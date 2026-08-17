"""0007_incident_lifecycle

§5.3 + §5.4's v3.0 columns + §5.13. incident table; alert gets lifecycle
columns (incident_id, version_number, supersedes_alert_id, change_reason,
lifecycle_status, estimated_onset_at, signature); the partial unique index
that makes "two active versions of one incident" a database error, not an
operational ambiguity; backfill every pre-existing alert into its own
single-version incident.

Down-migration note (§5.13): safe — drops columns, no data loss for v2.1
features, since this only ADDS to the base-spec alert table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-16
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE incident (
            id            BIGSERIAL PRIMARY KEY,
            label         TEXT NOT NULL,
            incident_type TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'active',
            origin_source TEXT NOT NULL REFERENCES alert_source(source_id),
            opened_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            closed_at     TIMESTAMPTZ,
            CHECK (status <> 'closed' OR closed_at IS NOT NULL)
        )
    """)
    op.execute('CREATE INDEX incident_status_ix ON incident (status)')

    op.execute('ALTER TABLE alert ADD COLUMN incident_id BIGINT REFERENCES incident(id)')
    op.execute('ALTER TABLE alert ADD COLUMN version_number SMALLINT NOT NULL DEFAULT 1')
    op.execute('ALTER TABLE alert ADD COLUMN supersedes_alert_id BIGINT REFERENCES alert(id)')
    op.execute('ALTER TABLE alert ADD COLUMN change_reason TEXT')
    op.execute("ALTER TABLE alert ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'draft'")
    op.execute('ALTER TABLE alert ADD COLUMN estimated_onset_at TIMESTAMPTZ')
    op.execute('ALTER TABLE alert ADD COLUMN signature BYTEA')

    op.execute("""
        ALTER TABLE alert ADD CONSTRAINT alert_version_needs_reason
          CHECK (version_number = 1 OR change_reason IS NOT NULL)
    """)
    op.execute("""
        ALTER TABLE alert ADD CONSTRAINT alert_version_needs_predecessor
          CHECK (version_number = 1 OR supersedes_alert_id IS NOT NULL)
    """)

    op.execute('CREATE INDEX alert_incident_ix ON alert (incident_id, version_number DESC)')
    op.execute('CREATE INDEX alert_lifecycle_ix ON alert (lifecycle_status)')
    op.execute("""
        CREATE UNIQUE INDEX alert_one_active_per_incident_uix
          ON alert (incident_id) WHERE lifecycle_status = 'active'
    """)

    # Backfill: every pre-existing alert gets its own single-version incident,
    # so `SELECT COUNT(*) FROM alert WHERE incident_id IS NULL` is 0 — the
    # Day-4 exit gate's exact assertion.
    op.execute("""
        INSERT INTO incident (label, incident_type, status, origin_source, opened_at)
        SELECT 'BACKFILL-' || a.id, 'unknown', 'active', a.source_id, a.ingested_at
        FROM alert a
        WHERE a.incident_id IS NULL
    """)
    op.execute("""
        UPDATE alert a
        SET incident_id = i.id, lifecycle_status = 'active'
        FROM incident i
        WHERE i.label = 'BACKFILL-' || a.id AND a.incident_id IS NULL
    """)


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS alert_one_active_per_incident_uix')
    op.execute('DROP INDEX IF EXISTS alert_lifecycle_ix')
    op.execute('DROP INDEX IF EXISTS alert_incident_ix')
    op.execute('ALTER TABLE alert DROP CONSTRAINT IF EXISTS alert_version_needs_predecessor')
    op.execute('ALTER TABLE alert DROP CONSTRAINT IF EXISTS alert_version_needs_reason')
    op.execute('ALTER TABLE alert DROP COLUMN IF EXISTS signature')
    op.execute('ALTER TABLE alert DROP COLUMN IF EXISTS estimated_onset_at')
    op.execute('ALTER TABLE alert DROP COLUMN IF EXISTS lifecycle_status')
    op.execute('ALTER TABLE alert DROP COLUMN IF EXISTS change_reason')
    op.execute('ALTER TABLE alert DROP COLUMN IF EXISTS supersedes_alert_id')
    op.execute('ALTER TABLE alert DROP COLUMN IF EXISTS version_number')
    op.execute('ALTER TABLE alert DROP COLUMN IF EXISTS incident_id')
    op.execute('DROP TABLE IF EXISTS incident')
