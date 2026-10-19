"""Prescription alerts are independent from ML predictions."""
from alembic import op


revision = "0014_phase5_prescription_alerts"
down_revision = "0013_phase5_pending_invoice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE alertes_prescription
        ALTER COLUMN prediction_id DROP NOT NULL,
        ALTER COLUMN facture_id DROP NOT NULL;
    ALTER TABLE alertes_prescription
        ADD COLUMN IF NOT EXISTS ordonnance_id TEXT REFERENCES ordonnances(ordonnance_id)
            ON DELETE CASCADE,
        ADD COLUMN IF NOT EXISTS type_alerte TEXT NOT NULL DEFAULT 'FACTURE',
        ADD COLUMN IF NOT EXISTS utilisateur_id BIGINT REFERENCES utilisateurs(utilisateur_id);
    CREATE INDEX IF NOT EXISTS ix_alertes_prescription_ordonnance
        ON alertes_prescription(ordonnance_id);
    CREATE INDEX IF NOT EXISTS ix_alertes_prescription_type
        ON alertes_prescription(type_alerte);
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON alertes_prescription TO app_rw;
            GRANT USAGE, SELECT ON SEQUENCE alertes_prescription_alerte_regle_id_seq TO app_rw;
        END IF;
    END $$;
    """)


def downgrade() -> None:
    op.execute("""
    DROP INDEX IF EXISTS ix_alertes_prescription_type;
    DROP INDEX IF EXISTS ix_alertes_prescription_ordonnance;
    ALTER TABLE alertes_prescription
        DROP COLUMN IF EXISTS utilisateur_id,
        DROP COLUMN IF EXISTS type_alerte,
        DROP COLUMN IF EXISTS ordonnance_id;
    DELETE FROM alertes_prescription WHERE prediction_id IS NULL OR facture_id IS NULL;
    ALTER TABLE alertes_prescription
        ALTER COLUMN prediction_id SET NOT NULL,
        ALTER COLUMN facture_id SET NOT NULL;
    """)
