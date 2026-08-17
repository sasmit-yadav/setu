"""0004_alerts

Base spec §5.4 (v2.1 base columns only — the v3.0 lifecycle columns are added
by 0007, not here, so this migration matches what actually existed before the
operational-closure layer). alert + alert_quarantine + alert_translation.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-16
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE alert (
            id           BIGSERIAL PRIMARY KEY,
            external_id  TEXT,
            source_id    TEXT NOT NULL REFERENCES alert_source(source_id),
            cluster_id   BIGINT,
            severity     TEXT NOT NULL,
            headline     TEXT NOT NULL,
            body         TEXT NOT NULL,
            lang         TEXT NOT NULL,
            area         GEOMETRY(MultiPolygon, 4326) NOT NULL,
            effective_at TIMESTAMPTZ NOT NULL,
            expires_at   TIMESTAMPTZ,
            raw_checksum TEXT NOT NULL,
            etag         TEXT,
            ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (source_id, external_id)
        )
    """)
    op.execute('CREATE INDEX alert_area_gix ON alert USING GIST (area)')

    op.execute("""
        CREATE TABLE alert_quarantine (
            id         BIGSERIAL PRIMARY KEY,
            source_id  TEXT NOT NULL,
            raw        BYTEA NOT NULL,
            reason     TEXT NOT NULL,
            detail     TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE alert_translation (
            alert_id   BIGINT NOT NULL REFERENCES alert(id),
            lang       TEXT NOT NULL,
            headline   TEXT NOT NULL,
            body       TEXT NOT NULL,
            model_id   SMALLINT REFERENCES model_registry(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (alert_id, lang)
        )
    """)


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS alert_translation')
    op.execute('DROP TABLE IF EXISTS alert_quarantine')
    op.execute('DROP TABLE IF EXISTS alert')
