"""Merge account identity and provider rejection-reason migration heads."""

revision = "0023_merge_heads"
down_revision = ("0021_merge_users", "0022_provider_rejection_reason")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
