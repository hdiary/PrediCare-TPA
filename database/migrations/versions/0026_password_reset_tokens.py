"""Create password-reset token storage with least-privilege API grants."""
from alembic import op


revision = "0026_password_reset_tokens"
down_revision = "0025_first_login_password"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS reinitialisations_mdp (
            reset_id BIGSERIAL PRIMARY KEY,
            utilisateur_id BIGINT NOT NULL REFERENCES utilisateurs(utilisateur_id)
                ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            cree_le TIMESTAMPTZ NOT NULL DEFAULT now(),
            expire_le TIMESTAMPTZ NOT NULL,
            utilise_le TIMESTAMPTZ
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_reinitialisations_mdp_utilisateur
        ON reinitialisations_mdp (utilisateur_id)
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON reinitialisations_mdp TO app_rw;
                GRANT USAGE, SELECT ON SEQUENCE reinitialisations_mdp_reset_id_seq TO app_rw;
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reinitialisations_mdp")