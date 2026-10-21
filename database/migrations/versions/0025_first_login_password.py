"""Track accounts that must confirm or change their initial password."""
from alembic import op


revision = "0025_first_login_password"
down_revision = "0024_pending_invoice_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE utilisateurs
        ADD COLUMN mot_de_passe_a_changer BOOLEAN NOT NULL DEFAULT false
    """)
    op.execute("""
        UPDATE utilisateurs u
        SET mot_de_passe_a_changer = true
        WHERE u.derniere_connexion IS NULL
          AND EXISTS (
              SELECT 1 FROM utilisateurs_roles ur
              JOIN roles r ON r.role_id = ur.role_id
              WHERE ur.utilisateur_id = u.utilisateur_id
                AND r.nom_role <> 'administrateur'
          )
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE utilisateurs DROP COLUMN mot_de_passe_a_changer")