"""Dedicated contract RAG tables.

Revision ID: 0004_rag_tables
Revises: 0003_foreign_keys
"""
from alembic import op

revision = "0004_rag_tables"
down_revision = "0003_foreign_keys"
branch_labels = None
depends_on = None

# Initial vector size. Migration 0005 changes this to the configured BGE-M3 size.
EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(f"""
    CREATE TABLE rag_documents (
        id          BIGSERIAL PRIMARY KEY,
        contrat_id  TEXT REFERENCES contrats(contrat_id) ON DELETE CASCADE,
        formule     TEXT CHECK (formule IN ('ESSENTIEL', 'CONFORT', 'PREMIUM')),
        scope       TEXT NOT NULL CHECK (scope IN ('contract', 'formula', 'global')),
        filename    TEXT NOT NULL,
        sha256      CHAR(64) NOT NULL UNIQUE,
        version     INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
        n_pages     INTEGER,
        ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK (
            (scope = 'contract' AND contrat_id IS NOT NULL AND formule IS NULL)
            OR (scope = 'formula' AND contrat_id IS NULL AND formule IS NOT NULL)
            OR (scope = 'global' AND contrat_id IS NULL AND formule IS NULL)
        )
    );

    CREATE TABLE rag_chunks (
        id             BIGSERIAL PRIMARY KEY,
        document_id    BIGINT NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
        contrat_id     TEXT REFERENCES contrats(contrat_id) ON DELETE CASCADE,
        formule        TEXT CHECK (formule IN ('ESSENTIEL', 'CONFORT', 'PREMIUM')),
        scope          TEXT NOT NULL CHECK (scope IN ('contract', 'formula', 'global')),
        chunk_index    INTEGER NOT NULL,
        content        TEXT NOT NULL,
        embedding      vector({EMBEDDING_DIM}) NOT NULL,
        article        TEXT,
        guarantee_code TEXT,
        page_start     INTEGER,
        page_end       INTEGER,
        token_count    INTEGER,
        metadata       JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        CHECK (
            (scope = 'contract' AND contrat_id IS NOT NULL AND formule IS NULL)
            OR (scope = 'formula' AND contrat_id IS NULL AND formule IS NOT NULL)
            OR (scope = 'global' AND contrat_id IS NULL AND formule IS NULL)
        ),
        UNIQUE (document_id, chunk_index)
    );
    CREATE INDEX ix_rag_chunks_contract ON rag_chunks(contrat_id)
        WHERE contrat_id IS NOT NULL;
    CREATE INDEX ix_rag_chunks_formula ON rag_chunks(formule)
        WHERE formule IS NOT NULL;
    CREATE INDEX ix_rag_chunks_scope ON rag_chunks(scope);
    CREATE INDEX ix_rag_chunks_embedding ON rag_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);

    CREATE TABLE rag_semantic_cache (
        id              BIGSERIAL PRIMARY KEY,
        contrat_id      TEXT NOT NULL REFERENCES contrats(contrat_id) ON DELETE CASCADE,
        query_text      TEXT NOT NULL,
        query_embedding vector({EMBEDDING_DIM}) NOT NULL,
        answer          TEXT NOT NULL,
        sources         JSONB NOT NULL,
        hits            INTEGER NOT NULL DEFAULT 0,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        expires_at      TIMESTAMPTZ
    );
    CREATE INDEX ix_rag_cache_contract ON rag_semantic_cache(contrat_id);
    CREATE INDEX ix_rag_cache_embedding ON rag_semantic_cache
        USING hnsw (query_embedding vector_cosine_ops);

    CREATE TABLE rag_query_log (
        id             BIGSERIAL PRIMARY KEY,
        user_pseudo_id TEXT NOT NULL,
        role           TEXT NOT NULL,
        question_hash  CHAR(64) NOT NULL,
        tools_used     TEXT[] NOT NULL DEFAULT '{{}}',
        cache_hit      BOOLEAN NOT NULL DEFAULT FALSE,
        blocked        BOOLEAN NOT NULL DEFAULT FALSE,
        block_reason   TEXT,
        tokens_in      INTEGER,
        tokens_out     INTEGER,
        latency_ms     INTEGER,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE VIEW v_rag_contrat_formules AS
        SELECT contrat_id, formule FROM contrats;

    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON rag_documents, rag_chunks,
                rag_semantic_cache TO app_rw;
            GRANT USAGE, SELECT ON SEQUENCE rag_documents_id_seq,
                rag_chunks_id_seq, rag_semantic_cache_id_seq TO app_rw;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro') THEN
            GRANT SELECT ON rag_documents, rag_chunks TO agent_ro;
            GRANT SELECT ON v_rag_contrat_formules TO agent_ro;
            GRANT SELECT, INSERT, UPDATE ON rag_semantic_cache TO agent_ro;
            GRANT USAGE, SELECT ON SEQUENCE rag_semantic_cache_id_seq TO agent_ro;
            GRANT INSERT ON rag_query_log TO agent_ro;
            GRANT USAGE, SELECT ON SEQUENCE rag_query_log_id_seq TO agent_ro;
        END IF;
    END $$;
    """)


def downgrade() -> None:
    op.execute("""
    DROP VIEW IF EXISTS v_rag_contrat_formules;
    DROP TABLE IF EXISTS rag_query_log;
    DROP TABLE IF EXISTS rag_semantic_cache;
    DROP TABLE IF EXISTS rag_chunks;
    DROP TABLE IF EXISTS rag_documents;
    """)
