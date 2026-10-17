"""Expose the amounts needed for user-facing claim status answers.

Revision ID: 0007_agent_claim_amounts
Revises: 0006_agent_claim_status_view
"""
from alembic import op


revision = "0007_agent_claim_amounts"
down_revision = "0006_agent_claim_status_view"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE VIEW v_agent_claim_status AS
        SELECT assure_id, contrat_id, facture_id, date_reception, date_soin,
               date_traitement, type_facture, statut, montant_total,
               montant_pris_en_charge
        FROM factures;
    REVOKE ALL ON v_agent_claim_status FROM PUBLIC;
    GRANT SELECT ON v_agent_claim_status TO agent_ro;
    """)


def downgrade() -> None:
    op.execute("""
    CREATE OR REPLACE VIEW v_agent_claim_status AS
        SELECT assure_id, contrat_id, facture_id, date_reception, date_soin,
               date_traitement, type_facture, statut
        FROM factures;
    REVOKE ALL ON v_agent_claim_status FROM PUBLIC;
    GRANT SELECT ON v_agent_claim_status TO agent_ro;
    """)
