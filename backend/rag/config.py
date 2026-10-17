"""Environment-backed settings for the contract RAG service."""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class RagSettings:
    database_url: str
    agent_database_url: str
    embedding_model: str
    embedding_dim: int
    embedding_api_url: str
    llm_api_key: str
    llm_model: str
    llm_api_url: str
    llm_timeout_seconds: float
    top_k: int
    min_score: float
    cache_similarity_threshold: float
    cache_ttl_hours: int

    @classmethod
    def from_env(cls) -> "RagSettings":
        settings = cls(
            database_url=os.environ.get("DATABASE_URL", ""),
            agent_database_url=os.environ.get("AGENT_DATABASE_URL", ""),
            embedding_model=os.environ.get("EMBEDDING_MODEL", ""),
            embedding_dim=int(os.environ.get("EMBEDDING_DIM", "1024")),
            embedding_api_url=os.environ.get(
                "EMBEDDING_API_URL", "https://api.openai.com/v1/embeddings"),
            llm_api_key=os.environ.get("LLM_API_KEY", ""),
            llm_model=os.environ.get("LLM_MODEL", ""),
            llm_api_url=os.environ.get(
                "LLM_API_URL", "https://api.openai.com/v1/chat/completions"),
            llm_timeout_seconds=float(
                os.environ.get("LLM_TIMEOUT_SECONDS", "300")),
            top_k=int(os.environ.get("RAG_TOP_K", "6")),
            min_score=float(os.environ.get("RAG_MIN_SCORE", "0.35")),
            cache_similarity_threshold=float(
                os.environ.get("CACHE_SIMILARITY_THRESHOLD", "0.93")),
            cache_ttl_hours=int(os.environ.get("CACHE_TTL_HOURS", "24")),
        )
        if not settings.database_url:
            raise ValueError("DATABASE_URL is required for RAG operations")
        if not settings.embedding_model:
            raise ValueError("EMBEDDING_MODEL must be configured")
        if settings.llm_timeout_seconds <= 0:
            raise ValueError("LLM_TIMEOUT_SECONDS must be positive")
        if settings.embedding_dim < 1:
            raise ValueError("EMBEDDING_DIM must be a positive integer")
        if not 1 <= settings.top_k <= 50:
            raise ValueError("RAG_TOP_K must be between 1 and 50")
        if not 0.0 <= settings.min_score <= 1.0:
            raise ValueError("RAG_MIN_SCORE must be between 0 and 1")
        if not 0.0 <= settings.cache_similarity_threshold <= 1.0:
            raise ValueError(
                "CACHE_SIMILARITY_THRESHOLD must be between 0 and 1")
        if settings.cache_ttl_hours < 1:
            raise ValueError("CACHE_TTL_HOURS must be positive")
        return settings
