"""Add notification delivery state and phase 6 manager decisions."""
from alembic import op
import sqlalchemy as sa


revision = "0015_phase6_alert_delivery"
down_revision = "0014_phase5_prescription_alerts"
branch_labels = None
depends_on = None


def _decision_table() -> str:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    table = next(
        (name for name in ("decisions_gestionnaires", "decisions_gestionnaire")
         if name in tables),
        None,
    )
    if table is None:
        raise RuntimeError("No supported manager-decision table exists")
    return table


def upgrade() -> None:
    table = _decision_table()
    constraint = f"{table}_decision_check"
    op.execute(f"""
    ALTER TABLE alertes
        ADD COLUMN IF NOT EXISTS etat_notification TEXT NOT NULL DEFAULT 'NON_REQUISE'
            CHECK (etat_notification IN ('NON_REQUISE', 'EN_ATTENTE', 'ENVOYEE', 'ECHEC')),
        ADD COLUMN IF NOT EXISTS tentatives_notification SMALLINT NOT NULL DEFAULT 0
            CHECK (tentatives_notification BETWEEN 0 AND 3);

    ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{constraint}";
    ALTER TABLE "{table}"
        ADD CONSTRAINT "{constraint}"
        CHECK (decision IN (
            'VALIDER', 'REJETER', 'CONFIRMER_FRAUDE', 'ESCALADER',
            'valide', 'rejete', 'a_investiguer',
            'fraude_confirmee', 'faux_positif'
        ));
    ALTER TABLE "{table}"
        ADD COLUMN IF NOT EXISTS montant_economise BIGINT CHECK (montant_economise IS NULL OR montant_economise >= 0);

    GRANT SELECT, UPDATE ON alertes TO app_rw;
    GRANT SELECT, INSERT ON "{table}" TO app_rw;
    """)


def downgrade() -> None:
    table = _decision_table()
    constraint = f"{table}_decision_check"
    op.execute(f"""
    ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{constraint}";
    ALTER TABLE "{table}"
        ADD CONSTRAINT "{constraint}"
        CHECK (decision IN ('valide', 'rejete', 'a_investiguer'));
    ALTER TABLE "{table}" DROP COLUMN IF EXISTS montant_economise;
    ALTER TABLE alertes
        DROP COLUMN IF EXISTS tentatives_notification,
        DROP COLUMN IF EXISTS etat_notification;
    """)
