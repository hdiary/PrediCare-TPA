"""Persist refresh sessions so logout and token rotation take effect server-side.

Revision ID: 0011_auth_sessions
Revises: 0010_chat_api_and_provider_scope
"""
from alembic import op


revision = "0011_auth_sessions"
down_revision = "0010_chat_api_and_provider_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE auth_sessions (
        session_id  UUID PRIMARY KEY,
        user_id     BIGINT NOT NULL REFERENCES utilisateurs(utilisateur_id)
                    ON DELETE CASCADE,
        refresh_jti UUID NOT NULL UNIQUE,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        expires_at  TIMESTAMPTZ NOT NULL,
        revoked_at  TIMESTAMPTZ
    );
    CREATE INDEX ix_auth_sessions_user_active
        ON auth_sessions(user_id, expires_at)
        WHERE revoked_at IS NULL;

    GRANT SELECT, INSERT, UPDATE, DELETE ON auth_sessions TO app_rw;
    """)


def downgrade() -> None:
    op.execute("""
    REVOKE ALL ON auth_sessions FROM app_rw;
    DROP TABLE IF EXISTS auth_sessions;
    """)
