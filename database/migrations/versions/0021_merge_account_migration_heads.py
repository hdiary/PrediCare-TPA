"""Merge account identity and contract status migration branches."""
from alembic import op


revision = "0021_merge_users"
down_revision = ("0019_account_identity", "0020_agent_contract_status_view")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
