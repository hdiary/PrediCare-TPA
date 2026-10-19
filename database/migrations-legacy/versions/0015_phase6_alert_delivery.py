"""Add notification delivery state and phase 6 manager decisions."""
from alembic import op


revision = "0015_phase6_alert_delivery"
down_revision = "0014_phase5_prescription_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE alertes
        ADD COLUMN IF NOT EXISTS etat_notification TEXT NOT NULL DEFAULT 'NON_REQUISE'
            CHECK (etat_notification IN ('NON_REQUISE', 'EN_ATTENTE', 'ENVOYEE', 'ECHEC')),
        ADD COLUMN IF NOT EXISTS tentatives_notification SMALLINT NOT NULL DEFAULT 0
            CHECK (tentatives_notification BETWEEN 0 AND 3);

    ALTER TABLE decisions_gestionnaires DROP CONSTRAINT IF EXISTS decisions_gestionnaires_decision_check;
    ALTER TABLE decisions_gestionnaires
        ADD CONSTRAINT decisions_gestionnaires_decision_check
        CHECK (decision IN (
            'VALIDER', 'REJETER', 'CONFIRMER_FRAUDE', 'ESCALADER',
            'valide', 'rejete', 'a_investiguer',
            'fraude_confirmee', 'faux_positif'
        ));
    ALTER TABLE decisions_gestionnaires
        ADD COLUMN IF NOT EXISTS montant_economise BIGINT CHECK (montant_economise IS NULL OR montant_economise >= 0);

    GRANT SELECT, UPDATE ON alertes TO app_rw;
    GRANT SELECT, INSERT ON decisions_gestionnaires TO app_rw;
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE decisions_gestionnaires DROP CONSTRAINT IF EXISTS decisions_gestionnaires_decision_check;
    ALTER TABLE decisions_gestionnaires
        ADD CONSTRAINT decisions_gestionnaires_decision_check
        CHECK (decision IN ('valide', 'rejete', 'a_investiguer'));
    ALTER TABLE decisions_gestionnaires DROP COLUMN IF EXISTS montant_economise;
    ALTER TABLE alertes
        DROP COLUMN IF EXISTS tentatives_notification,
        DROP COLUMN IF EXISTS etat_notification;
    """)
