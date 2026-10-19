"""PII-minimizing RAG query audit."""
from hashlib import sha256
import time

from sqlalchemy import text
from sqlalchemy.engine import Engine


class QueryAudit:
    def __init__(self, engine: Engine):
        self.engine = engine

    def write(self, *, user_pseudo_id: str, role: str, question: str,
              tools_used: list[str], cache_hit: bool, blocked: bool,
              block_reason: str | None, tokens_in: int, tokens_out: int,
              started_at: float) -> None:
        query_hash = sha256(question.encode("utf-8")).hexdigest()
        query = text("""
            INSERT INTO rag_query_log
                (user_pseudo_id, role, question_hash, tools_used, cache_hit,
                 blocked, block_reason, tokens_in, tokens_out, latency_ms)
            VALUES
                (:user_pseudo_id, :role, :question_hash, :tools_used, :cache_hit,
                 :blocked, :block_reason, :tokens_in, :tokens_out, :latency_ms)
        """)
        with self.engine.begin() as connection:
            connection.execute(query, {
                "user_pseudo_id": user_pseudo_id,
                "role": role,
                "question_hash": query_hash,
                "tools_used": tools_used,
                "cache_hit": cache_hit,
                "blocked": blocked,
                "block_reason": block_reason,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": int((time.monotonic() - started_at) * 1000),
            })
