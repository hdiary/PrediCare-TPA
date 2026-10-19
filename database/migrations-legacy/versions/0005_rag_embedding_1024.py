"""Rebuild RAG vectors for the BGE-M3 1024-dimensional model.

Revision ID: 0005_rag_embedding_1024
Revises: 0004_rag_tables
"""
from alembic import op

revision = "0005_rag_embedding_1024"
down_revision = "0004_rag_tables"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 1024
PREVIOUS_EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.execute(f"""
    TRUNCATE TABLE rag_semantic_cache;
    DELETE FROM rag_documents;
    DELETE FROM documents_vectorises;
    DROP INDEX ix_rag_chunks_embedding;
    DROP INDEX ix_rag_cache_embedding;
    DROP INDEX ix_documents_embedding;
    ALTER TABLE rag_chunks DROP COLUMN embedding;
    ALTER TABLE rag_chunks
        ADD COLUMN embedding vector({EMBEDDING_DIM}) NOT NULL;
    ALTER TABLE rag_semantic_cache DROP COLUMN query_embedding;
    ALTER TABLE rag_semantic_cache
        ADD COLUMN query_embedding vector({EMBEDDING_DIM}) NOT NULL;
    ALTER TABLE documents_vectorises DROP COLUMN embedding;
    ALTER TABLE documents_vectorises
        ADD COLUMN embedding vector({EMBEDDING_DIM}) NOT NULL;
    """)
    op.execute(f"""
    CREATE INDEX ix_rag_chunks_embedding ON rag_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    CREATE INDEX ix_rag_cache_embedding ON rag_semantic_cache
        USING hnsw (query_embedding vector_cosine_ops);
    CREATE INDEX ix_documents_embedding ON documents_vectorises
        USING hnsw (embedding vector_cosine_ops);
    """)


def downgrade() -> None:
    op.execute(f"""
    TRUNCATE TABLE rag_semantic_cache;
    DELETE FROM rag_documents;
    DELETE FROM documents_vectorises;
    DROP INDEX ix_rag_chunks_embedding;
    DROP INDEX ix_rag_cache_embedding;
    DROP INDEX ix_documents_embedding;
    ALTER TABLE rag_chunks DROP COLUMN embedding;
    ALTER TABLE rag_chunks
        ADD COLUMN embedding vector({PREVIOUS_EMBEDDING_DIM}) NOT NULL;
    ALTER TABLE rag_semantic_cache DROP COLUMN query_embedding;
    ALTER TABLE rag_semantic_cache
        ADD COLUMN query_embedding vector({PREVIOUS_EMBEDDING_DIM}) NOT NULL;
    ALTER TABLE documents_vectorises DROP COLUMN embedding;
    ALTER TABLE documents_vectorises
        ADD COLUMN embedding vector({PREVIOUS_EMBEDDING_DIM}) NOT NULL;
    """)
    op.execute("""
    CREATE INDEX ix_rag_chunks_embedding ON rag_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    CREATE INDEX ix_rag_cache_embedding ON rag_semantic_cache
        USING hnsw (query_embedding vector_cosine_ops);
    CREATE INDEX ix_documents_embedding ON documents_vectorises
        USING hnsw (embedding vector_cosine_ops);
    """)
