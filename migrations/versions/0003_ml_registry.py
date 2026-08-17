"""0003_ml_registry

Base spec §5.11 (v2.1, unchanged). model_registry has to exist before
alert_translation (0004) and reach_prediction (0006) can FK into it.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-16
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE model_registry (
            id           SMALLSERIAL PRIMARY KEY,
            name         TEXT NOT NULL,
            version      TEXT NOT NULL,
            artifact_uri TEXT NOT NULL,
            metrics      JSONB NOT NULL,
            is_bootstrap BOOLEAN NOT NULL,
            trained_at   TIMESTAMPTZ NOT NULL,
            active       BOOLEAN NOT NULL DEFAULT false,
            UNIQUE (name, version)
        )
    """)


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS model_registry')
