"""0010_citizen_response

§5.8 + §5.13. citizen_response (C6 — the CHECK constraint that makes the
location-consent promise structural, not trusted) + assistance_case (D11f —
priority_factors is NOT NULL by Rule 10, a score cannot exist without its
stored inputs).

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-16
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE citizen_response (
            id               BIGSERIAL PRIMARY KEY,
            delivery_id      BIGINT NOT NULL REFERENCES delivery(id),
            alert_id         BIGINT NOT NULL REFERENCES alert(id),
            unit_id          BIGINT NOT NULL REFERENCES admin_unit(id),
            response_type    TEXT NOT NULL,
            free_text        TEXT,
            location         GEOGRAPHY(Point, 4326),
            location_consent BOOLEAN NOT NULL DEFAULT false,
            idempotency_key  TEXT NOT NULL,
            submitted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            received_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (idempotency_key),
            CHECK (location IS NULL OR location_consent = true)
        )
    """)
    op.execute('CREATE INDEX citizen_response_alert_ix ON citizen_response (alert_id, response_type)')
    op.execute('CREATE INDEX citizen_response_geom_gix ON citizen_response USING GIST (location)')

    op.execute("""
        CREATE TABLE assistance_case (
            id                  BIGSERIAL PRIMARY KEY,
            citizen_response_id BIGINT NOT NULL UNIQUE REFERENCES citizen_response(id),
            priority_score      NUMERIC NOT NULL CHECK (priority_score BETWEEN 0 AND 1),
            priority_factors    JSONB NOT NULL,
            model_version       TEXT NOT NULL,
            status              TEXT NOT NULL DEFAULT 'new',
            assigned_team       TEXT,
            assigned_by         BIGINT REFERENCES app_user(id),
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at         TIMESTAMPTZ,
            CHECK (status = 'new' OR assigned_team IS NOT NULL),
            CHECK (status <> 'closed' OR resolved_at IS NOT NULL)
        )
    """)
    op.execute("""
        CREATE INDEX assistance_status_priority_ix
          ON assistance_case (status, priority_score DESC)
    """)


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS assistance_case')
    op.execute('DROP TABLE IF EXISTS citizen_response')
