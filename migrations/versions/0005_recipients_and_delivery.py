"""0005_recipients_and_delivery

Base spec §5.6 (v2.1 base columns only — phone_hash/consent_source/
opted_out_at are v3.0, added by 0012 per Trap 11 and §5.13, not here).
recipient + the delivery_state enum + delivery.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-16
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE recipient (
            id             BIGSERIAL PRIMARY KEY,
            unit_id        BIGINT NOT NULL REFERENCES admin_unit(id),
            kind           TEXT NOT NULL,
            push_token     TEXT,
            email_enc      BYTEA,
            phone_enc      BYTEA,
            preferred_lang TEXT NOT NULL DEFAULT 'en',
            consented_at   TIMESTAMPTZ,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute('CREATE INDEX recipient_unit_ix ON recipient (unit_id)')

    op.execute("""
        CREATE TYPE delivery_state AS ENUM
          ('pending','queued','sent','delivered','acknowledged','failed','expired','escalated')
    """)

    op.execute("""
        CREATE TABLE delivery (
            id            BIGSERIAL PRIMARY KEY,
            alert_id      BIGINT NOT NULL REFERENCES alert(id),
            recipient_id  BIGINT NOT NULL REFERENCES recipient(id),
            channel_id    SMALLINT NOT NULL REFERENCES channel(id),
            attempt       SMALLINT NOT NULL DEFAULT 1,
            state         delivery_state NOT NULL DEFAULT 'pending',
            provider_ref  TEXT,
            simulated     BOOLEAN NOT NULL DEFAULT false,
            queued_at     TIMESTAMPTZ,
            sent_at       TIMESTAMPTZ,
            delivered_at  TIMESTAMPTZ,
            acked_at      TIMESTAMPTZ,
            failed_reason TEXT,
            UNIQUE (alert_id, recipient_id, channel_id, attempt)
        )
    """)
    op.execute('CREATE INDEX delivery_alert_state_ix ON delivery (alert_id, state)')
    op.execute('CREATE INDEX delivery_provider_ref_ix ON delivery (provider_ref)')


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS delivery')
    op.execute('DROP TYPE IF EXISTS delivery_state')
    op.execute('DROP TABLE IF EXISTS recipient')
