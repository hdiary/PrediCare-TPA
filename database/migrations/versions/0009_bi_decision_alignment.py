"""Associate each BI decision with the prediction it reviews.

Revision ID: 0009_bi_decision_alignment
Revises: 0008_bi_currency
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_bi_decision_alignment"
down_revision = "0008_bi_currency"
branch_labels = None
depends_on = None


def _pred_cols() -> dict:
    """predictions peut etre en anglais (0002) ou en francais (0005_api_tables)."""
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("predictions")}

    def pick(*names):
        return next(n for n in names if n in cols)

    return {
        "alert": pick("is_alert", "est_alerte"),
        "version": pick("model_version", "version_modele"),
        "created": pick("created_at", "date"),
    }


def upgrade() -> None:
    c = _pred_cols()
    op.execute(f"""
    CREATE OR REPLACE VIEW v_bi_factures AS
    WITH pred AS (
        SELECT DISTINCT ON (facture_id)
               prediction_id,
               facture_id,
               score,
               "{c['alert']}"   AS is_alert,
               "{c['version']}" AS model_version
        FROM predictions
        ORDER BY facture_id, "{c['created']}" DESC, prediction_id DESC
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
    c = _pred_cols()
    op.execute(f"""
    CREATE OR REPLACE VIEW v_bi_factures AS
    WITH pred AS (
        SELECT DISTINCT ON (facture_id)
               facture_id,
               score,
               "{c['alert']}"   AS is_alert,
               "{c['version']}" AS model_version
        FROM predictions
        ORDER BY facture_id, "{c['created']}" DESC, prediction_id DESC
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