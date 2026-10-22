"""Track password changes for the monthly self-service cooldown."""
from alembic import op


revision = "0027_password_change_cooldown"
down_revision = "0026_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE utilisateurs
        ADD COLUMN mot_de_passe_modifie_le TIMESTAMPTZ
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE utilisateurs DROP COLUMN mot_de_passe_modifie_le")