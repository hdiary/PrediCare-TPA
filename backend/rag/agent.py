"""Grounded contract-answer orchestration."""
from dataclasses import asdict, dataclass
import time

from rag.audit import QueryAudit
from rag.cache import SemanticCache
from rag.embeddings import EmbeddingClient
from rag.guardrails.input_filter import blocked_reason
from rag.guardrails.output_filter import contains_sensitive_data
from rag.llm import ChatCompletionClient
from rag.prompts import (NO_INFORMATION_ANSWER, SYSTEM_PROMPT,
                         build_user_prompt)
from rag.retriever import ContractRetriever
from rag.structured_answers import (answer_from_contract,
                                    answer_from_guarantee_table,
                                    is_direct_contract_question,
                                    is_exclusion_question,
                                    is_guarantee_table_question)


@dataclass(frozen=True)
class ChatSource:
    filename: str
    article: str | None
    page_start: int | None
    page_end: int | None
    score: float


@dataclass(frozen=True)
class ChatResponse:
    answer: str
    sources: list[ChatSource]
    blocked: bool = False


class RagAgent:
    def __init__(self, embeddings: EmbeddingClient,
                 retriever: ContractRetriever, llm: ChatCompletionClient,
                 cache: SemanticCache, audit: QueryAudit):
        self.embeddings = embeddings
        self.retriever = retriever
        self.llm = llm
        self.cache = cache
        self.audit = audit

    def answer(self, question: str, *, contract_id: str, user_pseudo_id: str,
               role: str) -> ChatResponse:
        if not question.strip():
            raise ValueError("Question must not be empty")
        if not contract_id or not user_pseudo_id or not role:
            raise ValueError("Authenticated user context is required")
        started_at = time.monotonic()
        reason = blocked_reason(question, contract_id)
        if reason:
            response = ChatResponse(
                "Je ne peux pas répondre à cette demande. "
                "Je reste limité à vos questions sur votre contrat.",
                [], blocked=True)
            self.audit.write(
                user_pseudo_id=user_pseudo_id, role=role, question=question,
                tools_used=[], cache_hit=False, blocked=True,
                block_reason=reason, tokens_in=0, tokens_out=0,
                started_at=started_at)
            return response

        query_embedding = self.embeddings.embed([question])[0]
        structured_question = is_guarantee_table_question(question)
        exclusion_question = is_exclusion_question(question)
        deterministic_question = (
            structured_question
            or exclusion_question
            or is_direct_contract_question(question)
        )
        if not deterministic_question:
            cached = self.cache.get(query_embedding, contract_id, question)
            if cached and not contains_sensitive_data(cached[0]):
                answer, source_data = cached
                sources = [ChatSource(**source) for source in source_data]
                self.audit.write(
                    user_pseudo_id=user_pseudo_id, role=role, question=question,
                    tools_used=["semantic_cache"], cache_hit=True, blocked=False,
                    block_reason=None, tokens_in=0, tokens_out=0,
                    started_at=started_at)
                return ChatResponse(answer, sources)

        chunks = self.retriever.search(
            query_embedding, contract_id,
            include_guarantee_table=structured_question,
            include_exclusions=exclusion_question)
        if not chunks:
            response = ChatResponse(NO_INFORMATION_ANSWER, [])
            self.audit.write(
                user_pseudo_id=user_pseudo_id, role=role, question=question,
                tools_used=["contract_search"], cache_hit=False, blocked=False,
                block_reason=None, tokens_in=0, tokens_out=0,
                started_at=started_at)
            return response

        structured_answer = answer_from_contract(question, chunks)
        if structured_answer is None:
            structured_answer = answer_from_guarantee_table(question, chunks)
        if structured_answer:
            answer, chunk = structured_answer
            source = ChatSource(
                filename=chunk.filename, article=chunk.article,
                page_start=chunk.page_start, page_end=chunk.page_end,
                score=chunk.score)
            answer = f"{answer}\n\nSources : [{chunk.source}]"
            self.audit.write(
                user_pseudo_id=user_pseudo_id, role=role, question=question,
                tools_used=[
                    "contract_search",
                    "exclusions" if exclusion_question else "structured_answer",
                ],
                cache_hit=False, blocked=False, block_reason=None, tokens_in=0,
                tokens_out=0, started_at=started_at)
            return ChatResponse(answer, [source])

        excerpts = [(chunk.source, chunk.content) for chunk in chunks]
        answer, tokens_in, tokens_out = self.llm.complete(
            SYSTEM_PROMPT, build_user_prompt(question, excerpts))
        if contains_sensitive_data(answer):
            answer = (
                "Je ne peux pas afficher de coordonnées ou de données "
                "d'identité. Veuillez contacter un gestionnaire.")
            sources: list[ChatSource] = []
        else:
            citations = ", ".join(f"[{chunk.source}]" for chunk in chunks)
            answer = f"{answer.rstrip()}\n\nSources : {citations}"
            sources = [
                ChatSource(
                    filename=chunk.filename, article=chunk.article,
                    page_start=chunk.page_start, page_end=chunk.page_end,
                    score=chunk.score)
                for chunk in chunks
            ]
            self.cache.put(
                question, query_embedding, contract_id, answer,
                [asdict(source) for source in sources])

        self.audit.write(
            user_pseudo_id=user_pseudo_id, role=role, question=question,
            tools_used=["contract_search", "llm"], cache_hit=False,
            blocked=False, block_reason=None, tokens_in=tokens_in,
            tokens_out=tokens_out, started_at=started_at)
        return ChatResponse(answer, sources)
