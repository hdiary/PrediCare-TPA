"""Authenticated RAG chat and per-user conversation history."""
import logging
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.types.json import Jsonb
from sqlalchemy.exc import SQLAlchemyError

from api.db import get_db
from api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])
_CHAT_ROLES = {"assure", "professionnel_sante"}
_HISTORY_LIMIT = 30
_MESSAGES_PER_CONVERSATION = 100


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID | None = None
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Le message ne peut pas être vide")
        return value.strip()


def _require_chat_role(user: dict) -> None:
    if user["role"] not in _CHAT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le chat est réservé aux assurés et professionnels de santé",
        )


def _conversation_messages(conn, conversation_ids: list[UUID]) -> dict[str, list[dict]]:
    if not conversation_ids:
        return {}
    rows = conn.execute(
        "SELECT id, conversation_id, role, content, sources, created_at "
        "FROM chat_messages WHERE conversation_id = ANY(%s) "
        "ORDER BY conversation_id, created_at DESC, id DESC",
        (conversation_ids,),
    ).fetchall()
    result: dict[str, list[dict]] = {str(item): [] for item in conversation_ids}
    for row in rows:
        messages = result[str(row["conversation_id"])]
        if len(messages) >= _MESSAGES_PER_CONVERSATION:
            continue
        messages.append({
            "id": str(row["id"]),
            "role": row["role"],
            "content": row["content"],
            "timestamp": row["created_at"].isoformat(),
            "sources": row["sources"] or [],
            "feedback": None,
        })
    for messages in result.values():
        messages.reverse()
    return result


@router.get("/history")
def history(
    user: dict = Depends(get_current_user),
    conn=Depends(get_db),
):
    _require_chat_role(user)
    conversations = conn.execute(
        "SELECT id, title, updated_at, "
        "(SELECT content FROM chat_messages m "
        " WHERE m.conversation_id = c.id "
        " ORDER BY m.created_at DESC, m.id DESC LIMIT 1) AS last_message "
        "FROM chat_conversations c WHERE user_id = %s "
        "ORDER BY updated_at DESC LIMIT %s",
        (user["user_id"], _HISTORY_LIMIT),
    ).fetchall()
    conversation_ids = [row["id"] for row in conversations]
    messages = _conversation_messages(conn, conversation_ids)
    return {
        "conversations": [
            {
                "id": str(row["id"]),
                "title": row["title"],
                "last_message": row["last_message"] or "",
                "updated_at": row["updated_at"].isoformat(),
                "messages": messages[str(row["id"])],
            }
            for row in conversations
        ]
    }


def _source_output(source) -> dict:
    return {
        "document": source.filename,
        "page": source.page_start or source.page_end,
        "excerpt": source.article or "Référence documentaire citée dans la réponse.",
    }


def _resolve_agent_scope(conn, user: dict) -> tuple[str | None, str | None, str]:
    if user["role"] == "assure":
        assure_id = user.get("assure_id")
        if not assure_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Aucun assuré n'est rattaché à ce compte",
            )
        row = conn.execute(
            "SELECT contrat_id FROM assures "
            "WHERE assure_id = %s AND date_radiation IS NULL",
            (assure_id,),
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Aucun contrat actif n'est rattaché à ce compte",
            )
        return row["contrat_id"], assure_id, assure_id

    prestataire_id = user.get("prestataire_id")
    if not prestataire_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aucun prestataire n'est rattaché à ce compte",
        )
    row = conn.execute(
        "SELECT prestataire_id FROM prestataires "
        "WHERE prestataire_id = %s AND statut = 'ACTIF'",
        (prestataire_id,),
    ).fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aucun prestataire actif n'est rattaché à ce compte",
        )
    return None, None, prestataire_id


@router.post("")
def send_message(
    body: ChatRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    conn=Depends(get_db),
):
    _require_chat_role(user)

    if body.conversation_id:
        existing = conn.execute(
            "SELECT id FROM chat_conversations "
            "WHERE id = %s AND user_id = %s",
            (body.conversation_id, user["user_id"]),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Conversation introuvable")
        conversation_id = body.conversation_id
    else:
        conversation_id = uuid4()

    contract_id, assure_id, user_pseudo_id = _resolve_agent_scope(conn, user)
    agent = getattr(request.app.state, "rag_agent", None)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="L'assistant RAG n'est pas configuré",
        )

    try:
        result = agent.answer(
            body.message,
            contract_id=contract_id,
            user_pseudo_id=user_pseudo_id,
            role=user["role"],
            assure_id=assure_id,
            prestataire_id=(
                user.get("prestataire_id")
                if user["role"] == "professionnel_sante"
                else None
            ),
        )
    except httpx.TimeoutException as exc:
        logger.warning("rag_timeout user_id=%s", user["user_id"])
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Le service de réponse a dépassé le délai autorisé",
        ) from exc
    except httpx.HTTPError as exc:
        logger.error("rag_upstream_error user_id=%s error_type=%s",
                     user["user_id"], type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Le service de réponse est indisponible",
        ) from exc
    except SQLAlchemyError as exc:
        logger.error("rag_database_error user_id=%s error_type=%s",
                     user["user_id"], type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Les données de l'assistant sont temporairement indisponibles",
        ) from exc
    except (ValueError, RuntimeError) as exc:
        logger.error("rag_response_error user_id=%s error_type=%s",
                     user["user_id"], type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="L'assistant n'a pas pu produire une réponse valide",
        ) from exc

    sources = [_source_output(source) for source in result.sources]
    user_message_id = uuid4()
    assistant_message_id = uuid4()
    title = body.message[:80]
    with conn.transaction():
        if not body.conversation_id:
            conn.execute(
                "INSERT INTO chat_conversations (id, user_id, title) "
                "VALUES (%s, %s, %s)",
                (conversation_id, user["user_id"], title),
            )
        conn.execute(
            "INSERT INTO chat_messages "
            "(id, conversation_id, role, content, sources) "
            "VALUES (%s, %s, 'user', %s, '[]'::jsonb), "
            "(%s, %s, 'assistant', %s, %s)",
            (
                user_message_id, conversation_id, body.message,
                assistant_message_id, conversation_id, result.answer,
                Jsonb(sources),
            ),
        )
        conn.execute(
            "UPDATE chat_conversations SET updated_at = now() WHERE id = %s",
            (conversation_id,),
        )

    return {
        "conversation_id": str(conversation_id),
        "answer": result.answer,
        "sources": sources,
        "blocked": result.blocked,
    }
