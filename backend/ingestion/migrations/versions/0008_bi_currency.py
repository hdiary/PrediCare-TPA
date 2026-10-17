"""Expose invoice currency to BI so monetary amounts have an explicit unit.

Revision ID: 0008_bi_currency
Revises: 0007_agent_claim_amounts, 0003_bi_views
"""
from alembic import op


revision = "0008_bi_currency"
down_revision = ("0007_agent_claim_amounts", "0003_bi_views")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE VIEW v_bi_factures AS
    WITH pred AS (
        SELECT DISTINCT ON (facture_id)
               facture_id, score, threshold, is_alert, model_version
        FROM predictions
        ORDER BY facture_id, created_at DESC, prediction_id DESC
    ),
    dec AS (
        SELECT DISTINCT ON (facture_id)
               facture_id, decision, decided_at, decision_id
        FROM decisions_gestionnaires
        ORDER BY facture_id, decided_at DESC, decision_id DESC
    )
    SELECT f.facture_id,
           f.date_facture,
           f.type_facture,
           f.montant_total,
           f.montant_eligible,
           pr.prestataire_id,
           pr.nom            AS prestataire_nom,
           p.score,
           p.is_alert,
           p.model_version,
           d.decision,
           d.decided_at,
           l.est_fraude,
           l.est_valide,
           f.devise
    FROM factures f
    JOIN prestataires pr      ON pr.prestataire_id = f.prestataire_id
    LEFT JOIN pred p          ON p.facture_id = f.facture_id
    LEFT JOIN dec d           ON d.facture_id = f.facture_id
    LEFT JOIN labels_fraude l ON l.facture_id = f.facture_id;
    """)


def downgrade() -> None:
    op.execute("""
    DROP VIEW v_bi_factures;
    CREATE VIEW v_bi_factures AS
    WITH pred AS (
        SELECT DISTINCT ON (facture_id)
               facture_id, score, threshold, is_alert, model_version
        FROM predictions
        ORDER BY facture_id, created_at DESC, prediction_id DESC
    ),
    dec AS (
        SELECT DISTINCT ON (facture_id)
               facture_id, decision, decided_at, decision_id
        FROM decisions_gestionnaires
        ORDER BY facture_id, decided_at DESC, decision_id DESC
    )
    SELECT f.facture_id,
           f.date_facture,
           f.type_facture,
           f.montant_total,
           f.montant_eligible,
           pr.prestataire_id,
           pr.nom            AS prestataire_nom,
           p.score,
           p.is_alert,
           p.model_version,
           d.decision,
           d.decided_at,
           l.est_fraude,
           l.est_valide
    FROM factures f
    JOIN prestataires pr      ON pr.prestataire_id = f.prestataire_id
    LEFT JOIN pred p          ON p.facture_id = f.facture_id
    LEFT JOIN dec d           ON d.facture_id = f.facture_id
    LEFT JOIN labels_fraude l ON l.facture_id = f.facture_id;
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metabase_ro') THEN
            GRANT SELECT ON v_bi_factures TO metabase_ro;
        END IF;
    END $$;
    """)
