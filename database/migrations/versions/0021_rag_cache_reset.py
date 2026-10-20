"""Clear cached RAG answers generated with the hard-coded contract example."""
from alembic import op


revision = "0021_rag_cache_reset"
down_revision = "0020_agent_contract_status_view"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM rag_semantic_cache")


def downgrade() -> None:
    pass
