"""Add pseudonymous login identifiers and encrypted account identity records."""

from alembic import op


revision = "0019_account_identity"
down_revision = "0018_bi_snapshot_unification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE utilisateurs ADD COLUMN identifiant TEXT;
    CREATE UNIQUE INDEX ux_utilisateurs_identifiant
        ON utilisateurs (identifiant) WHERE identifiant IS NOT NULL;

    CREATE TABLE utilisateurs_identites (
        utilisateur_id BIGINT PRIMARY KEY
            REFERENCES utilisateurs (utilisateur_id) ON DELETE CASCADE,
        donnees_chiffrees BYTEA NOT NULL,
        key_version SMALLINT NOT NULL CHECK (key_version >= 1),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    GRANT SELECT, INSERT, UPDATE, DELETE ON utilisateurs_identites TO app_rw;
    """)


def downgrade() -> None:
    op.execute("""
    REVOKE ALL ON utilisateurs_identites FROM app_rw;
    DROP TABLE utilisateurs_identites;
    DROP INDEX ux_utilisateurs_identifiant;
    ALTER TABLE utilisateurs DROP COLUMN identifiant;
    """)
