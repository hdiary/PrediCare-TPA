"""Expose mapped rejection reasons to the authenticated provider RAG."""
from alembic import op


revision = "0022_provider_rejection_reason"
down_revision = "0021_rag_cache_reset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE VIEW v_agent_provider_rejection_reasons AS
        SELECT facture_id, prestataire_id, motif_rejet
        FROM factures
        WHERE statut = 'REJETEE' AND motif_rejet IS NOT NULL;
    REVOKE ALL ON v_agent_provider_rejection_reasons FROM PUBLIC;
    GRANT SELECT ON v_agent_provider_rejection_reasons TO agent_ro;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_agent_provider_rejection_reasons")
