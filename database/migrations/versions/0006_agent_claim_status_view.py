"""Expose a minimal read-only invoice status view to the RAG agent.

Revision ID: 0006_agent_claim_status_view
Revises: 0005_rag_embedding_1024
"""
from alembic import op


revision = "0006_agent_claim_status_view"
down_revision = "0005_rag_embedding_1024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE VIEW v_agent_claim_status AS
        SELECT assure_id, contrat_id, facture_id, date_reception, date_soin,
               date_traitement, type_facture, statut
        FROM factures;
    REVOKE ALL ON v_agent_claim_status FROM PUBLIC;
    GRANT SELECT ON v_agent_claim_status TO agent_ro;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_agent_claim_status")
