"""Phase 4 registry and missing persistence tables.

The legacy SQL files under db/migrations are not executed by Alembic. This
migration carries forward only their missing API tables. Existing business
tables and the existing predictions table are left untouched.
"""
from alembic import op


revision = "0012_phase4_model_registry"
down_revision = "0011_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS model_versions (
        version       TEXT PRIMARY KEY,
        artifact_path TEXT NOT NULL,
        sha256        CHAR(64) NOT NULL CHECK (sha256 ~ '^[0-9a-fA-F]{64}$'),
        metrics       JSONB NOT NULL DEFAULT '{}'::jsonb,
        status        TEXT NOT NULL CHECK (status IN ('CANDIDAT', 'ACTIF', 'ARCHIVE')),
        metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
        trained_at    TIMESTAMPTZ,
        activated_at  TIMESTAMPTZ,
        active_par    BIGINT REFERENCES utilisateurs(utilisateur_id)
    );
    CREATE UNIQUE INDEX IF NOT EXISTS uq_model_versions_one_active
        ON model_versions(status) WHERE status = 'ACTIF';

    CREATE TABLE IF NOT EXISTS explications_shap (
        prediction_id BIGINT PRIMARY KEY REFERENCES predictions(prediction_id)
                      ON DELETE CASCADE,
        facture_id    TEXT NOT NULL REFERENCES factures(facture_id),
        valeurs       JSONB NOT NULL
    );

    CREATE TABLE IF NOT EXISTS calculs_remboursement (
        calcul_id                 BIGSERIAL PRIMARY KEY,
        facture_id                TEXT NOT NULL UNIQUE REFERENCES factures(facture_id)
                                  ON DELETE CASCADE,
        montant_reclame           BIGINT NOT NULL CHECK (montant_reclame >= 0),
        montant_calcule           BIGINT NOT NULL CHECK (montant_calcule >= 0),
        montant_rembourse         BIGINT NOT NULL CHECK (montant_rembourse >= 0),
        reste_a_charge            BIGINT NOT NULL CHECK (reste_a_charge >= 0),
        details                   JSONB NOT NULL DEFAULT '{}'::jsonb,
        cree_le                   TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS factures_rejetees (
        rejet_id       BIGSERIAL PRIMARY KEY,
        facture_id     TEXT,
        assure_id      TEXT,
        prestataire_id TEXT,
        codes          JSONB NOT NULL,
        details        JSONB NOT NULL DEFAULT '{}'::jsonb,
        utilisateur_id BIGINT REFERENCES utilisateurs(utilisateur_id),
        cree_le        TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS alertes (
        alerte_id      BIGSERIAL PRIMARY KEY,
        facture_id     TEXT REFERENCES factures(facture_id) ON DELETE CASCADE,
        type           TEXT NOT NULL,
        priorite       TEXT NOT NULL CHECK (priorite IN ('FAIBLE', 'MOYENNE', 'HAUTE')),
        codes          JSONB NOT NULL DEFAULT '[]'::jsonb,
        statut         TEXT NOT NULL DEFAULT 'EN_ATTENTE',
        cree_le        TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS alertes_prescription (
        alerte_regle_id BIGSERIAL PRIMARY KEY,
        prediction_id   BIGINT NOT NULL REFERENCES predictions(prediction_id)
                        ON DELETE CASCADE,
        facture_id      TEXT NOT NULL REFERENCES factures(facture_id)
                        ON DELETE CASCADE,
        regle_code      TEXT NOT NULL,
        severite        TEXT NOT NULL,
        message         TEXT NOT NULL,
        details         JSONB,
        cree_le         TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS ix_alertes_prescription_facture
        ON alertes_prescription(facture_id);

    CREATE TABLE IF NOT EXISTS journal_audit (
        audit_id       BIGSERIAL PRIMARY KEY,
        horodatage     TIMESTAMPTZ NOT NULL DEFAULT now(),
        type_evenement TEXT NOT NULL,
        utilisateur_id BIGINT REFERENCES utilisateurs(utilisateur_id),
        type_entite    TEXT NOT NULL,
        entite_id      TEXT,
        nom_modele     TEXT,
        version_modele TEXT,
        entree         JSONB,
        sortie         JSONB
    );
    CREATE INDEX IF NOT EXISTS ix_journal_audit_horodatage
        ON journal_audit(horodatage DESC);

    REVOKE ALL ON model_versions, explications_shap, calculs_remboursement,
        factures_rejetees, alertes, alertes_prescription, journal_audit FROM PUBLIC;
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON model_versions,
                explications_shap, calculs_remboursement, factures_rejetees,
                alertes, alertes_prescription, journal_audit TO app_rw;
            GRANT USAGE, SELECT ON SEQUENCE calculs_remboursement_calcul_id_seq,
                factures_rejetees_rejet_id_seq, alertes_alerte_id_seq,
                alertes_prescription_alerte_regle_id_seq, journal_audit_audit_id_seq
                TO app_rw;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro') THEN
            REVOKE ALL ON model_versions, explications_shap, calculs_remboursement,
                factures_rejetees, alertes, alertes_prescription, journal_audit FROM agent_ro;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ml_ro') THEN
            REVOKE ALL ON model_versions, explications_shap, calculs_remboursement,
                factures_rejetees, alertes, alertes_prescription, journal_audit FROM ml_ro;
        END IF;
    END $$;
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS journal_audit;
    DROP TABLE IF EXISTS alertes_prescription;
    DROP TABLE IF EXISTS alertes;
    DROP TABLE IF EXISTS factures_rejetees;
    DROP TABLE IF EXISTS calculs_remboursement;
    DROP TABLE IF EXISTS explications_shap;
    DROP INDEX IF EXISTS uq_model_versions_one_active;
    DROP TABLE IF EXISTS model_versions;
    """)
