"""Allow invoices waiting for a manager when scoring is unavailable."""
from alembic import op

revision = "0013_phase5_pending_invoice"
down_revision = "0012_phase4_model_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE factures DROP CONSTRAINT IF EXISTS factures_statut_check")
    op.execute("""
        ALTER TABLE factures ADD CONSTRAINT factures_statut_check
        CHECK (statut IN ('PAYEE', 'REJETEE', 'EN_COURS', 'EN_ATTENTE_GESTIONNAIRE'))
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE factures DROP CONSTRAINT IF EXISTS factures_statut_check")
    op.execute("""
        ALTER TABLE factures ADD CONSTRAINT factures_statut_check
        CHECK (statut IN ('PAYEE', 'REJETEE', 'EN_COURS'))
    """)
