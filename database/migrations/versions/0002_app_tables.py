"""app tables: predictions, SHAP, decisions, vector documents, audit log

Revision ID: 0002_app_tables
Revises: <LAST_REVISION_ID>   # <- replace with the value from alembic_version
"""
from alembic import op

revision = "0002_app_tables"
down_revision = "p1_0004"
branch_labels = None
depends_on = None

# --- Adapt to the real schema (check with \d factures / \d contrats) ---
FACTURE_ID_TYPE = "TEXT"      # type of factures.facture_id
FACTURE_ID_COL = "facture_id"
CONTRAT_ID_TYPE = "TEXT"      # type of contrats.contrat_id
CONTRAT_ID_COL = "contrat_id"
EMBEDDING_DIM = 1536          # must match EMBEDDING_MODEL (confirm with the RAG team)


def upgrade():
    # ---------- Predictions ----------
    op.execute(f"""
    CREATE TABLE predictions (
        prediction_id  BIGSERIAL PRIMARY KEY,
        facture_id     {FACTURE_ID_TYPE} NOT NULL
                       REFERENCES factures({FACTURE_ID_COL}) ON DELETE CASCADE,
        model_version  TEXT NOT NULL,
        score          NUMERIC(6,5) NOT NULL CHECK (score BETWEEN 0 AND 1),
        threshold      NUMERIC(6,5) NOT NULL,
        is_alert       BOOLEAN NOT NULL,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (facture_id, model_version)
    );
    CREATE INDEX ix_predictions_facture ON predictions(facture_id);
    CREATE INDEX ix_predictions_alert ON predictions(is_alert, created_at DESC);
    """)

    # ---------- SHAP explanations ----------
    op.execute("""
    CREATE TABLE shap_explanations (
        shap_id        BIGSERIAL PRIMARY KEY,
        prediction_id  BIGINT NOT NULL
                       REFERENCES predictions(prediction_id) ON DELETE CASCADE,
        feature_name   TEXT NOT NULL,
        feature_value  TEXT,
        shap_value     DOUBLE PRECISION NOT NULL,
        rank           SMALLINT NOT NULL,
        UNIQUE (prediction_id, feature_name)
    );
    CREATE INDEX ix_shap_prediction ON shap_explanations(prediction_id, rank);
    """)

    # ---------- Manager decisions ----------
    op.execute(f"""
    CREATE TABLE decisions_gestionnaires (
        decision_id    BIGSERIAL PRIMARY KEY,
        facture_id     {FACTURE_ID_TYPE} NOT NULL
                       REFERENCES factures({FACTURE_ID_COL}) ON DELETE CASCADE,
        prediction_id  BIGINT REFERENCES predictions(prediction_id) ON DELETE SET NULL,
        user_id        TEXT NOT NULL,          -- application user, never a real name
        decision       TEXT NOT NULL
                       CHECK (decision IN ('valide','rejete','a_investiguer')),
        commentaire    TEXT,
        decided_at     TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_decisions_facture ON decisions_gestionnaires(facture_id, decided_at DESC);
    """)

    # ---------- Vectorised documents (RAG) ----------
    op.execute(f"""
    CREATE TABLE documents_vectorises (
        doc_id       BIGSERIAL PRIMARY KEY,
        contrat_id   {CONTRAT_ID_TYPE} REFERENCES contrats({CONTRAT_ID_COL}) ON DELETE SET NULL,
        source_file  TEXT NOT NULL,
        chunk_index  INTEGER NOT NULL,
        content      TEXT NOT NULL,
        metadata     JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        embedding    vector({EMBEDDING_DIM}) NOT NULL,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (source_file, chunk_index)
    );
    CREATE INDEX ix_documents_embedding
        ON documents_vectorises USING hnsw (embedding vector_cosine_ops);
    """)

    # ---------- Audit log (append-only) ----------
    op.execute("""
    CREATE TABLE audit_log (
        audit_id     BIGSERIAL PRIMARY KEY,
        occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        actor        TEXT NOT NULL,            -- user id or service name
        actor_role   TEXT,
        action       TEXT NOT NULL,            -- e.g. 'view_identity', 'decision', 'login'
        object_type  TEXT,
        object_id    TEXT,
        details      JSONB NOT NULL DEFAULT '{}'::jsonb
    );
    CREATE INDEX ix_audit_time ON audit_log(occurred_at DESC);
    CREATE INDEX ix_audit_actor ON audit_log(actor, occurred_at DESC);

    CREATE FUNCTION audit_log_immutable() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'audit_log is append-only';
    END;
    $$ LANGUAGE plpgsql;

    CREATE TRIGGER trg_audit_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
    CREATE TRIGGER trg_audit_no_truncate
        BEFORE TRUNCATE ON audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION audit_log_immutable();
    """)

    # ---------- Grants (only for roles that exist) ----------
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
            GRANT SELECT, INSERT, UPDATE ON predictions, shap_explanations,
                  documents_vectorises TO app_rw;
            GRANT SELECT, INSERT ON decisions_gestionnaires TO app_rw;
            GRANT SELECT, INSERT ON audit_log TO app_rw;
            GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_rw;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ml_ro') THEN
            GRANT SELECT ON predictions, shap_explanations TO ml_ro;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro') THEN
            GRANT SELECT ON documents_vectorises TO agent_ro;
        END IF;
    END $$;
    """)


def downgrade():
    op.execute("""
    DROP TABLE IF EXISTS audit_log CASCADE;
    DROP FUNCTION IF EXISTS audit_log_immutable();
    DROP TABLE IF EXISTS documents_vectorises CASCADE;
    DROP TABLE IF EXISTS decisions_gestionnaires CASCADE;
    DROP TABLE IF EXISTS shap_explanations CASCADE;
    DROP TABLE IF EXISTS predictions CASCADE;
    """)