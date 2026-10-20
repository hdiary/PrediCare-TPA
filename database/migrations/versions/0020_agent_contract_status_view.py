"""Expose minimal contract status data to the RAG agent."""
from alembic import op


revision = "0020_agent_contract_status_view"
down_revision = "0019_normalize_user_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE VIEW v_agent_contract_status AS
        SELECT a.assure_id, c.contrat_id, c.statut
        FROM assures AS a
        JOIN contrats AS c ON c.contrat_id = a.contrat_id;
    REVOKE ALL ON v_agent_contract_status FROM PUBLIC;
    GRANT SELECT ON v_agent_contract_status TO agent_ro;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_agent_contract_status")
