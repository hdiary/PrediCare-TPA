"""Grounded contract-answer orchestration."""
from dataclasses import asdict, dataclass
import json
import time
from typing import Any

from rag.audit import QueryAudit
from rag.cache import SemanticCache
from rag.embeddings import EmbeddingClient
from rag.guardrails.input_filter import blocked_reason
from rag.guardrails.output_filter import contains_sensitive_data
from rag.llm import ChatCompletionClient
from rag.prompts import NO_INFORMATION_ANSWER, SYSTEM_PROMPT
from rag.retriever import ContractRetriever
from rag.structured_answers import (answer_from_contract,
                                    answer_from_guarantee_table,
                                    is_direct_contract_question,
                                    is_exclusion_question,
                                    is_guarantee_table_question)
from rag.toolkit import AgentToolkit


_MAX_TOOL_CALLS = 4


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

    def answer(self, question: str, *, contract_id: str | None,
               user_pseudo_id: str, role: str,
               assure_id: str | None = None,
               prestataire_id: str | None = None) -> ChatResponse:
        if not question.strip():
            raise ValueError("Question must not be empty")
        if (not user_pseudo_id or not role
                or (not contract_id and not prestataire_id)
                or (assure_id and prestataire_id)):
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

        claim_question = AgentToolkit.is_claim_question(question)
        if claim_question and not (assure_id or prestataire_id):
            response = ChatResponse(
                "Le suivi des factures nécessite l'identifiant pseudonymisé "
                "de l'assuré connecté. En CLI, fournissez-le avec "
                "--assure-id ; ce mode est réservé aux essais locaux.",
                [])
            self.audit.write(
                user_pseudo_id=user_pseudo_id, role=role, question=question,
                tools_used=["claim_tool_unavailable"], cache_hit=False,
                blocked=False, block_reason=None, tokens_in=0, tokens_out=0,
                started_at=started_at)
            return response

        if (prestataire_id
                and AgentToolkit.is_reimbursement_total_question(question)):
            response = ChatResponse(
                "Je ne peux pas calculer un total de remboursements à partir "
                "des factures d'un professionnel de santé.", [])
            self.audit.write(
                user_pseudo_id=user_pseudo_id, role=role, question=question,
                tools_used=["provider_total_not_available"], cache_hit=False,
                blocked=False, block_reason=None, tokens_in=0, tokens_out=0,
                started_at=started_at)
            return response

        if AgentToolkit.is_claim_status_question(question):
            toolkit = AgentToolkit(
                embeddings=self.embeddings,
                retriever=self.retriever,
                engine=self.retriever.engine,
                contract_id=contract_id or "",
                assure_id=assure_id,
                prestataire_id=prestataire_id,
            )
            answer = toolkit.recent_claims_answer()
            source_label = (
                "historique des factures du prestataire connecté"
                if prestataire_id
                else "historique des factures du compte"
            )
            answer = f"{answer}\n\nSource : {source_label}."
            self.audit.write(
                user_pseudo_id=user_pseudo_id, role=role, question=question,
                tools_used=["search_my_claims"], cache_hit=False,
                blocked=False, block_reason=None, tokens_in=0, tokens_out=0,
                started_at=started_at)
            return ChatResponse(answer, [])

        structured_question = is_guarantee_table_question(question)
        exclusion_question = is_exclusion_question(question)
        deterministic_question = (not prestataire_id and (
            structured_question
            or exclusion_question
            or is_direct_contract_question(question)
        ))
        query_embedding = (
            self.embeddings.embed([question])[0]
            if deterministic_question or not claim_question
            else None
        )
        if (not deterministic_question and not claim_question
                and not prestataire_id):
            if query_embedding is None or not contract_id:
                raise RuntimeError("Query embedding was not initialized")
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

        sources: list[ChatSource] = []
        tools_used: list[str] = []
        tokens_in = 0
        tokens_out = 0
        if deterministic_question:
            if query_embedding is None:
                raise RuntimeError("Query embedding was not initialized")
            chunks = self.retriever.search(
                query_embedding, contract_id or "",
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

        toolkit = AgentToolkit(
            embeddings=self.embeddings,
            retriever=self.retriever,
            engine=self.retriever.engine,
            contract_id=contract_id or "",
            assure_id=assure_id,
            prestataire_id=prestataire_id,
        )
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": question}
        ]
        answer = ""
        tool_call_count = 0
        while True:
            assistant_message, input_tokens, output_tokens = (
                self.llm.complete_with_tools(
                    SYSTEM_PROMPT, messages, toolkit.definitions)
            )
            tokens_in += input_tokens
            tokens_out += output_tokens
            tool_calls = assistant_message.get("tool_calls") or []
            if not tool_calls:
                content = assistant_message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("LLM returned an empty final answer")
                answer = content.strip()
                break

            tool_call_count += len(tool_calls)
            if tool_call_count > _MAX_TOOL_CALLS:
                raise RuntimeError(
                    f"Agent exceeded the limit of {_MAX_TOOL_CALLS} tool calls")
            messages.append(assistant_message)
            for tool_call in tool_calls:
                function = tool_call.get("function")
                if not isinstance(function, dict):
                    raise ValueError("LLM returned an invalid tool call")
                name = function.get("name")
                arguments_json = function.get("arguments")
                if not isinstance(name, str) or not isinstance(
                        arguments_json, str):
                    raise ValueError("LLM returned invalid tool arguments")
                try:
                    arguments = json.loads(arguments_json)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        "LLM returned malformed tool argument JSON") from error
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be a JSON object")
                result = toolkit.execute(name, arguments)
                sources.extend(
                    ChatSource(
                        filename=chunk.filename,
                        article=chunk.article,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        score=chunk.score,
                    )
                    for chunk in result.sources
                )
                tools_used.append(name)
                call_id = tool_call.get("id")
                if not isinstance(call_id, str):
                    raise ValueError("LLM returned a tool call without an ID")
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result.content,
                })

        if contains_sensitive_data(answer):
            answer = (
                "Je ne peux pas afficher de coordonnées ou de données "
                "d'identité. Veuillez contacter un gestionnaire.")
            sources = []
        else:
            if sources:
                citations = ", ".join(dict.fromkeys(
                    f"[{source.filename}, {source.article or 'Sans article'}, "
                    f"page {source.page_start or '?'}]"
                    for source in sources))
                answer = f"{answer.rstrip()}\n\nSources : {citations}"
            if "search_my_claims" in tools_used:
                answer = (
                    f"{answer.rstrip()}\n\n"
                    "Source : historique des factures du compte."
                )
            if (not claim_question and "search_my_claims" not in tools_used
                    and not prestataire_id):
                if query_embedding is None or not contract_id:
                    raise RuntimeError("Query embedding was not initialized")
                self.cache.put(
                    question, query_embedding, contract_id, answer,
                    [asdict(source) for source in sources])

        self.audit.write(
            user_pseudo_id=user_pseudo_id, role=role, question=question,
            tools_used=tools_used + ["llm"], cache_hit=False,
            blocked=False, block_reason=None, tokens_in=tokens_in,
            tokens_out=tokens_out, started_at=started_at)
        return ChatResponse(answer, sources)
