"""0014_recipient_pwa_device_index

Citizen PWA push-token registration (POST /api/v1/citizen/device) needs
somewhere to write, and there is no app_user -> recipient link in the
schema — recipients come from CSV import or SMS keyword, never from login.
A citizen session only carries unit_scope_id, so a device registration
find-or-creates one recipient per (unit_id, kind='citizen_pwa') and upserts
its push_token there. This migration adds the unique index that upsert
relies on.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-21
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial, not a blanket UNIQUE(unit_id, kind): CSV import (kind='citizen')
    # legitimately inserts many recipients per unit. Only 'citizen_pwa' — a
    # kind value nothing else writes — is meant to be at most one per unit.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS recipient_unit_citizen_pwa_uix "
        "ON recipient (unit_id) WHERE kind = 'citizen_pwa'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS recipient_unit_citizen_pwa_uix")
