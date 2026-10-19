"""Associate each BI decision with the prediction it reviews.

Revision ID: 0009_bi_decision_alignment
Revises: 0008_bi_currency
"""
from alembic import op


revision = "0009_bi_decision_alignment"
down_revision = "0008_bi_currency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE VIEW v_bi_factures AS
    WITH pred AS (
        SELECT DISTINCT ON (facture_id)
               prediction_id, facture_id, score, threshold, is_alert,
               model_version
        FROM predictions
        ORDER BY facture_id, created_at DESC, prediction_id DESC
    ),
    dec AS (
        SELECT DISTINCT ON (prediction_id)
               prediction_id, decision, decided_at, decision_id
        FROM decisions_gestionnaires
        ORDER BY prediction_id, decided_at DESC, decision_id DESC
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
    LEFT JOIN dec d           ON d.prediction_id = p.prediction_id
    LEFT JOIN labels_fraude l ON l.facture_id = f.facture_id;
    """)


def downgrade() -> None:
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
