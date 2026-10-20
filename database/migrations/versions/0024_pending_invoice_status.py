"""Allow invoices waiting for a manager to be stored."""
from alembic import op


revision = "0024_pending_invoice_status"
down_revision = "0023_merge_migration_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE factures DROP CONSTRAINT IF EXISTS factures_statut_check")
    op.execute("""
        ALTER TABLE factures ADD CONSTRAINT factures_statut_check
        CHECK (statut IN ('PAYEE', 'REJETEE', 'EN_COURS', 'EN_ATTENTE_GESTIONNAIRE'))
    """)


def downgrade() -> None:
    op.execute(
        "UPDATE factures SET statut = 'EN_COURS' "
        "WHERE statut = 'EN_ATTENTE_GESTIONNAIRE'"
    )
    op.execute("ALTER TABLE factures DROP CONSTRAINT IF EXISTS factures_statut_check")
    op.execute("""
        ALTER TABLE factures ADD CONSTRAINT factures_statut_check
        CHECK (statut IN ('PAYEE', 'REJETEE', 'EN_COURS'))
    """)
