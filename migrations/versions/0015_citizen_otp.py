"""0015_citizen_otp

Citizen PWA login is phone + OTP, not email. Challenges live in Postgres so
tests and the API share one store (no Redis dependency on the auth path).
The code itself is stored as SHA-256; the raw digits never persist.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-22
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS citizen_otp_challenge (
            phone_hash BYTEA PRIMARY KEY,
            code_hash  TEXT NOT NULL,
            attempts   SMALLINT NOT NULL DEFAULT 0,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS citizen_otp_challenge")
