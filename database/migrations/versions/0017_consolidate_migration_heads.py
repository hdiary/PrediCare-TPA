"""Fusionne la chaîne API active et la chaîne BI/RAG historique."""

from alembic import op


revision = "0017_consolidate_migration_heads"
down_revision = "0016_bi_materialized_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Les deux branches créent déjà ces objets. Cette migration ne fait que
    # fournir un head unique pour les installations neuves et existantes.
    pass


def downgrade() -> None:
    pass
