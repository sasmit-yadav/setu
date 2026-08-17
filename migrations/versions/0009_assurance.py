"""0009_assurance

§5.7 + §5.13 (Rule 8's source of truth) + §5.10's incident_id addition to
audit_event. assurance_event enum, delivery_event (UNIQUE(delivery_id,
event_type) is what makes duplicate provider webhooks a no-op instead of an
inflated ladder), assurance_level() as a function so the ladder can never
drift from its own rows, channel_capability + its seed.

Down-migration note (§5.13): dropping the enum requires dropping the table
first — handled explicitly below, in that order.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-16
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE assurance_event AS ENUM (
            'delivery_attempted', 'provider_accepted', 'device_delivered',
            'notification_opened', 'acknowledged', 'citizen_response'
        )
    """)

    op.execute("""
        CREATE TABLE delivery_event (
            id          BIGSERIAL PRIMARY KEY,
            delivery_id BIGINT NOT NULL REFERENCES delivery(id),
            event_type  assurance_event NOT NULL,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            source      TEXT NOT NULL,
            evidence_id TEXT,
            metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
            UNIQUE (delivery_id, event_type)
        )
    """)
    op.execute('CREATE INDEX delivery_event_delivery_ix ON delivery_event (delivery_id)')
    op.execute('CREATE INDEX delivery_event_type_ix ON delivery_event (event_type)')

    op.execute("""
        CREATE OR REPLACE FUNCTION assurance_level(p_delivery_id BIGINT) RETURNS SMALLINT AS $$
          SELECT COALESCE(MAX(CASE event_type
              WHEN 'delivery_attempted'   THEN 0
              WHEN 'provider_accepted'    THEN 1
              WHEN 'device_delivered'     THEN 2
              WHEN 'notification_opened'  THEN 3
              WHEN 'acknowledged'         THEN 4
              WHEN 'citizen_response'     THEN 5 END), -1)
          FROM delivery_event WHERE delivery_id = p_delivery_id;
        $$ LANGUAGE sql STABLE
    """)

    # channel_capability — the honesty table. Rule 8: fixed per unresolved TIER,
    # not one blanket reason per channel (this schema fixes finding #3: a single
    # not_applicable_reason column would print the email tracking-pixel sentence
    # against SIREN's "device_delivered" rung too).
    op.execute("""
        CREATE TABLE channel_capability_tier (
            channel_id             SMALLINT NOT NULL REFERENCES channel(id),
            tier                   TEXT NOT NULL CHECK (tier IN
                                     ('provider_accept','device_delivered','opened','acknowledgement')),
            supported              BOOLEAN NOT NULL,
            device_delivered_source TEXT,
            not_applicable_reason  TEXT,
            PRIMARY KEY (channel_id, tier),
            CHECK (supported OR not_applicable_reason IS NOT NULL)
        )
    """)

    # Convenience view matching §5.2's original single-row-per-channel shape,
    # for code/UI that wants "does this channel support X" without a pivot.
    op.execute("""
        CREATE VIEW channel_capability AS
        SELECT
            channel_id,
            bool_or(tier = 'provider_accept' AND supported)   AS supports_provider_accept,
            bool_or(tier = 'device_delivered' AND supported)  AS supports_device_delivered,
            bool_or(tier = 'opened' AND supported)             AS supports_opened,
            bool_or(tier = 'acknowledgement' AND supported)    AS supports_acknowledgement,
            max(device_delivered_source) FILTER (WHERE tier = 'device_delivered') AS device_delivered_source
        FROM channel_capability_tier
        GROUP BY channel_id
    """)

    op.execute('ALTER TABLE audit_event ADD COLUMN incident_id BIGINT REFERENCES incident(id)')
    op.execute('CREATE INDEX audit_incident_ix ON audit_event (incident_id, occurred_at)')


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS audit_incident_ix')
    op.execute('ALTER TABLE audit_event DROP COLUMN IF EXISTS incident_id')
    op.execute('DROP VIEW IF EXISTS channel_capability')
    op.execute('DROP TABLE IF EXISTS channel_capability_tier')
    op.execute('DROP FUNCTION IF EXISTS assurance_level(BIGINT)')
    op.execute('DROP TABLE IF EXISTS delivery_event')
    op.execute('DROP TYPE IF EXISTS assurance_event')
