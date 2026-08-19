"""0013_auth

Authentication and session storage for Part 26's RBAC matrix.

WHY THIS EXISTS: before this migration every one of the API's endpoints was
unauthenticated, including POST /alerts/{id}/dispatch (which fans an alert out
to every consented recipient) and POST /alerts/{id}/approve (which took
approver_id from the REQUEST BODY, so any caller could approve as any officer).
That made every governance guarantee in the platform unverifiable: Rule 12's
machine-vs-human provenance, F3's Four-Eyes quorum, and the
UNIQUE (alert_id, approver_id) constraint are all real mechanisms that mean
nothing if the caller's identity is self-asserted. §12.2's privacy design
(relay_node never sees assistance cases, auditor gets aggregate-only) is
likewise unenforceable without a role attached to the request.

Adds:
  app_user.password_hash  — bcrypt via passlib. NULLable, because the seeded
                            demo accounts are created without credentials and
                            have them set out-of-band; a NULL hash means "this
                            account cannot log in", never "any password works".
  app_user.last_login_at  — operational visibility, and the cheapest possible
                            signal that a seeded account is being used.
  refresh_token           — server-side refresh sessions so a token can be
                            REVOKED. A stateless refresh JWT cannot be, and an
                            un-revocable long-lived credential on a system that
                            can order an evacuation is not acceptable.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-19
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE app_user
            ADD COLUMN IF NOT EXISTS password_hash TEXT,
            ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ
        """
    )

    # Refresh sessions are stored, not stateless, specifically so they can be
    # revoked — on logout, on role change, or on suspected compromise.
    # token_hash, never the token: a stolen database dump must not yield
    # usable credentials.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS refresh_token (
            id           BIGSERIAL PRIMARY KEY,
            user_id      BIGINT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
            token_hash   TEXT NOT NULL UNIQUE,
            issued_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at   TIMESTAMPTZ NOT NULL,
            revoked_at   TIMESTAMPTZ,
            user_agent   TEXT,
            CHECK (expires_at > issued_at)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS refresh_token_user_ix ON refresh_token (user_id) "
        "WHERE revoked_at IS NULL"
    )

    # A contact reveal is itself an audit event (Part 26's last row, §12.2).
    # The ledger already records it; this index makes "who revealed whose
    # contact details, and when" a fast query rather than a full scan, because
    # an auditor asking that question is the whole point of the role existing.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS audit_event_actor_ix
            ON audit_event (actor, occurred_at DESC)
            WHERE actor IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS audit_event_actor_ix")
    op.execute("DROP INDEX IF EXISTS refresh_token_user_ix")
    op.execute("DROP TABLE IF EXISTS refresh_token")
    op.execute(
        """
        ALTER TABLE app_user
            DROP COLUMN IF EXISTS last_login_at,
            DROP COLUMN IF EXISTS password_hash
        """
    )
