"""Construct the RAG agent with the least-privileged database role."""

from sqlalchemy import create_engine

from rag.agent import RagAgent
from rag.audit import QueryAudit
from rag.cache import SemanticCache
from rag.config import RagSettings
from rag.embeddings import EmbeddingClient
from rag.llm import ChatCompletionClient
from rag.retriever import ContractRetriever


def create_agent() -> RagAgent:
    settings = RagSettings.from_env()
    database_url = settings.agent_database_url
    if not database_url:
        raise ValueError("AGENT_DATABASE_URL is required for the RAG agent")
    if database_url.startswith(("postgresql://", "postgres://")):
        database_url = database_url.replace(
            "postgres://", "postgresql+psycopg://", 1
        ).replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(database_url)
    embeddings = EmbeddingClient(
        settings.llm_api_key, settings.embedding_model,
        settings.embedding_dim, settings.embedding_api_url)
    llm = ChatCompletionClient(
        settings.llm_api_key, settings.llm_model, settings.llm_api_url,
        settings.llm_timeout_seconds)
    retriever = ContractRetriever(engine, settings.top_k, settings.min_score)
    cache = SemanticCache(
        engine, settings.cache_similarity_threshold, settings.cache_ttl_hours)
    audit = QueryAudit(engine)
    return RagAgent(embeddings, retriever, llm, cache, audit)
