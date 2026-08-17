"""0011_relay

§5.9 + §5.13. relay_node (seeded, Rule 3) + relay_confirmation
(confirmed_by_human, households_claimed — named _claimed not _reached on
purpose, Rule 9). The human_relay/community_relay channel rows and the
relay_nodes.sql seed itself land in data/seeds, not here — Rule 3 again.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-16
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE relay_node (
            id          BIGSERIAL PRIMARY KEY,
            unit_id     BIGINT NOT NULL REFERENCES admin_unit(id),
            kind        TEXT NOT NULL,
            name        TEXT NOT NULL,
            phone_enc   BYTEA NOT NULL,
            phone_hash  BYTEA NOT NULL,
            active      BOOLEAN NOT NULL DEFAULT true,
            seeded_from TEXT NOT NULL DEFAULT 'data/seeds/relay_nodes.sql'
        )
    """)
    op.execute('CREATE INDEX relay_node_unit_ix ON relay_node (unit_id) WHERE active')

    op.execute("""
        CREATE TABLE relay_confirmation (
            id                 BIGSERIAL PRIMARY KEY,
            delivery_id        BIGINT NOT NULL REFERENCES delivery(id),
            relay_node_id      BIGINT NOT NULL REFERENCES relay_node(id),
            unit_id            BIGINT NOT NULL REFERENCES admin_unit(id),
            confirmed_by_human BOOLEAN NOT NULL DEFAULT true,
            method             TEXT NOT NULL,
            households_claimed INTEGER,
            confirmed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (delivery_id, relay_node_id)
        )
    """)


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS relay_confirmation')
    op.execute('DROP TABLE IF EXISTS relay_node')
