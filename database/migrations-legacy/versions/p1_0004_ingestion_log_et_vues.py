"""P1 0004 - ingestion_log and views (ref_codes, v_factures_features)

Revision ID: p1_0004
Revises: p1_0003
"""
from alembic import op

revision = "p1_0004"
down_revision = "p1_0003"
branch_labels = None
depends_on = None

UPGRADE_SQL = """
-- One row per loaded file. (fichier, sha256) is unique: loading the same file
-- content twice is skipped by load.py, which is what makes loading idempotent.
CREATE TABLE ingestion_log (
    id                  BIGSERIAL PRIMARY KEY,
    fichier             TEXT NOT NULL,
    sha256              CHAR(64) NOT NULL,
    date_ingestion      TIMESTAMPTZ NOT NULL DEFAULT now(),
    lignes_lues         INTEGER NOT NULL,
    lignes_inserees     INTEGER NOT NULL,
    lignes_mises_a_jour INTEGER NOT NULL,
    lignes_rejetees     INTEGER NOT NULL DEFAULT 0,  -- rejected upstream by clean.py
    statut              TEXT NOT NULL DEFAULT 'OK' CHECK (statut IN ('OK')),
    UNIQUE (fichier, sha256)
);

-- Actes and medicaments share one code space (86 codes, no overlap).
CREATE VIEW ref_codes AS
    SELECT code_acte AS code, 'ACTE'::text AS type_ligne, libelle,
           tarif_min, tarif_reference, tarif_max
    FROM referentiel_actes
    UNION ALL
    SELECT code_medicament, 'MEDICAMENT', libelle,
           NULL::bigint, prix_reference, NULL::bigint
    FROM referentiel_medicaments;

-- The ONLY invoice columns the model may see. The decision columns
-- (montant_pris_en_charge, reste_a_charge, statut, motif_rejet,
-- date_traitement) result from the historical decision and leak the label.
CREATE VIEW v_factures_features AS
    SELECT facture_id, numero_facture, prestataire_id, assure_id, contrat_id,
           ordonnance_id, type_facture, date_soin, heure_soin, date_facture,
           date_reception, canal_reception, mode_reglement,
           attestation_pec_id, entente_prealable_id, devise, nb_lignes,
           montant_total, montant_eligible
    FROM factures;

GRANT SELECT ON ingestion_log, ref_codes, v_factures_features TO app_rw;
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(UPGRADE_SQL)


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql("DROP VIEW IF EXISTS v_factures_features")
    bind.exec_driver_sql("DROP VIEW IF EXISTS ref_codes")
    bind.exec_driver_sql("DROP TABLE IF EXISTS ingestion_log")
