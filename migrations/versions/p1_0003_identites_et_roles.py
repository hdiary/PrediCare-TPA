"""P1 0003 - encrypted identities table and access roles

Roles are NOLOGIN group roles. Login users (created by P3 in docker-compose or
an admin script) are made members of them.

    app_rw           read/write on every P1 table EXCEPT identites_chiffrees
    identity_reader  SELECT on identites_chiffrees only (P3 alert display)
    agent_ro         created here, granted nothing yet: J3 adds read-only views
                     limited to the logged-in insured person (P4 agent)

Nobody else, PUBLIC included, can read identites_chiffrees.

Revision ID: p1_0003
Revises: p1_0002
"""
from alembic import op

revision = "p1_0003"
down_revision = "p1_0002"
branch_labels = None
depends_on = None

BUSINESS_TABLES = [
    "referentiel_actes", "referentiel_medicaments", "garanties",
    "prestataires", "grille_tarifaire", "contrats", "assures", "ordonnances",
    "ordonnance_lignes", "factures", "lignes_facture", "labels_fraude",
    "labels_prestataires",
]

UPGRADE_SQL = """
-- Personal data of insured persons: ONE encrypted JSON per person (Fernet,
-- encrypted by the application BEFORE insertion; the key never reaches SQL).
CREATE TABLE identites_chiffrees (
    assure_id         TEXT PRIMARY KEY
        REFERENCES assures (assure_id) ON DELETE CASCADE,
    donnees_chiffrees BYTEA NOT NULL,
    key_version       SMALLINT NOT NULL CHECK (key_version >= 1),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['app_rw', 'identity_reader', 'agent_ro'] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            -- quote_ident, not format(): the driver reads a percent sign
            -- inside the SQL text as a parameter placeholder
            EXECUTE 'CREATE ROLE ' || quote_ident(r) || ' NOLOGIN';
        END IF;
    END LOOP;
END $$;

REVOKE ALL ON identites_chiffrees FROM PUBLIC;
GRANT SELECT ON identites_chiffrees TO identity_reader;
GRANT USAGE ON SCHEMA public TO app_rw, identity_reader, agent_ro;
"""


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(UPGRADE_SQL)
    tables = ", ".join(BUSINESS_TABLES)
    bind.exec_driver_sql(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tables} TO app_rw")


def downgrade() -> None:
    bind = op.get_bind()
    tables = ", ".join(BUSINESS_TABLES)
    bind.exec_driver_sql(
        f"REVOKE ALL ON {tables} FROM app_rw")
    bind.exec_driver_sql("DROP TABLE IF EXISTS identites_chiffrees")
    # roles are kept: they may own privileges granted by other migrations
