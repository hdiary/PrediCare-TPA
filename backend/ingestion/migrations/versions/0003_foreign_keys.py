from alembic import op

revision = "0003_foreign_keys"
down_revision = "0002_app_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE lignes_facture
      ADD CONSTRAINT fk_lignes_facture
      FOREIGN KEY (facture_id) REFERENCES factures(facture_id) ON DELETE CASCADE;
    ALTER TABLE factures
      ADD CONSTRAINT fk_factures_assure
      FOREIGN KEY (assure_id) REFERENCES assures(assure_id) ON DELETE RESTRICT;
    ALTER TABLE identites_chiffrees
      ADD CONSTRAINT fk_identites_assure
      FOREIGN KEY (assure_id) REFERENCES assures(assure_id) ON DELETE CASCADE;
    CREATE INDEX IF NOT EXISTS ix_factures_assure ON factures(assure_id);
    CREATE INDEX IF NOT EXISTS ix_lignes_facture_facture ON lignes_facture(facture_id);
    """)


def downgrade():
    op.execute("""
    ALTER TABLE identites_chiffrees DROP CONSTRAINT IF EXISTS fk_identites_assure;
    ALTER TABLE factures DROP CONSTRAINT IF EXISTS fk_factures_assure;
    ALTER TABLE lignes_facture DROP CONSTRAINT IF EXISTS fk_lignes_facture;
    """)