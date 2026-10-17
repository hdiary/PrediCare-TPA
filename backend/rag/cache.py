"""Contract-scoped semantic response cache."""
import json

from sqlalchemy import text
from sqlalchemy.engine import Engine

from rag.retriever import _vector_literal


class SemanticCache:
    def __init__(self, engine: Engine, similarity_threshold: float,
                 ttl_hours: int):
        self.engine = engine
        self.similarity_threshold = similarity_threshold
        self.ttl_hours = ttl_hours

    def get(self, query_embedding: list[float], contract_id: str,
            query_text: str):
        query = text("""
            SELECT id, answer, sources,
                   1 - (query_embedding <=> CAST(:embedding AS vector)) AS score
            FROM rag_semantic_cache
            WHERE contrat_id = :contract_id
              AND lower(trim(query_text)) = lower(trim(:query_text))
              AND (expires_at IS NULL OR expires_at > now())
            ORDER BY query_embedding <=> CAST(:embedding AS vector)
            LIMIT 1
        """)
        with self.engine.begin() as connection:
            row = connection.execute(query, {
                "embedding": _vector_literal(query_embedding),
                "contract_id": contract_id,
                "query_text": query_text,
            }).mappings().first()
            if row is None or float(row["score"]) < self.similarity_threshold:
                return None
            connection.execute(text(
                "UPDATE rag_semantic_cache SET hits = hits + 1 WHERE id = :id"),
                {"id": row["id"]})
        sources = row["sources"]
        if isinstance(sources, str):
            sources = json.loads(sources)
        return row["answer"], sources

    def put(self, query_text: str, query_embedding: list[float],
            contract_id: str, answer: str, sources: list[dict]) -> None:
        query = text("""
            INSERT INTO rag_semantic_cache
                (contrat_id, query_text, query_embedding, answer, sources, expires_at)
            VALUES
                (:contract_id, :query_text, CAST(:embedding AS vector), :answer,
                 CAST(:sources AS jsonb), now() + make_interval(hours => :ttl_hours))
        """)
        with self.engine.begin() as connection:
            connection.execute(query, {
                "contract_id": contract_id,
                "query_text": query_text,
                "embedding": _vector_literal(query_embedding),
                "answer": answer,
                "sources": json.dumps(sources, ensure_ascii=False),
                "ttl_hours": self.ttl_hours,
            })
