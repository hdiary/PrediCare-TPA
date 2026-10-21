"""Encryption and retention for persisted chat history."""
import base64
import json
import re
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from api.config import get_settings

CHAT_HISTORY_RETENTION_DAYS = 180
_ENCRYPTED_PREFIX = "enc:v1:"
_REDACTED_TITLE = f"{_ENCRYPTED_PREFIX}redacted"
_BATCH_SIZE = 250


class ChatEncryptionUnavailableError(RuntimeError):
    """The chat history encryption key is absent or invalid."""


def _fernet() -> Fernet:
    key = (get_settings().chat_encryption_key or "").strip()
    if not key:
        raise ChatEncryptionUnavailableError(
            "CHAT_ENCRYPTION_KEY is not configured")
    if re.fullmatch(r"[0-9a-fA-F]{64}", key):
        key = base64.urlsafe_b64encode(bytes.fromhex(key)).decode()
    try:
        return Fernet(key.encode())
    except (TypeError, ValueError) as exc:
        raise ChatEncryptionUnavailableError(
            "CHAT_ENCRYPTION_KEY is invalid") from exc


def encrypt_text(value: str) -> str:
    encrypted = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return _ENCRYPTED_PREFIX + encrypted


def decrypt_text(value: str) -> str:
    if value == _REDACTED_TITLE:
        return "Conversation"
    if not value.startswith(_ENCRYPTED_PREFIX):
        raise ChatEncryptionUnavailableError(
            "Chat history contains unencrypted text")
    try:
        return _fernet().decrypt(
            value[len(_ENCRYPTED_PREFIX):].encode("ascii")
        ).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise ChatEncryptionUnavailableError(
            "Chat history could not be decrypted") from exc


def encrypt_sources(sources: list[dict[str, Any]]) -> str:
    serialized = json.dumps(sources, ensure_ascii=False, separators=(",", ":"))
    return encrypt_text(serialized)


def decrypt_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, str):
        raise ChatEncryptionUnavailableError(
            "Chat history sources are not encrypted")
    try:
        sources = json.loads(decrypt_text(value))
    except json.JSONDecodeError as exc:
        raise ChatEncryptionUnavailableError(
            "Chat history sources are invalid") from exc
    if not isinstance(sources, list) or any(
            not isinstance(source, dict) for source in sources):
        raise ChatEncryptionUnavailableError(
            "Chat history sources are invalid")
    return sources


def secure_existing_chat_history(conn) -> tuple[int, int]:
    """Encrypt pre-existing plaintext rows in bounded, idempotent batches."""
    _fernet()
    conversations_encrypted = 0
    messages_encrypted = 0

    while True:
        with conn.transaction():
            rows = conn.execute(
                "SELECT id, title FROM chat_conversations "
                "WHERE title NOT LIKE %s ORDER BY created_at "
                "LIMIT %s FOR UPDATE",
                (f"{_ENCRYPTED_PREFIX}%", _BATCH_SIZE),
            ).fetchall()
            for row in rows:
                conn.execute(
                    "UPDATE chat_conversations SET title = %s WHERE id = %s",
                    (encrypt_text(row["title"]), row["id"]),
                )
        conversations_encrypted += len(rows)
        if not rows:
            break

    while True:
        with conn.transaction():
            rows = conn.execute(
                "SELECT id, content, sources FROM chat_messages "
                "WHERE content NOT LIKE %s "
                "OR jsonb_typeof(sources) <> 'string' "
                "OR sources #>> '{}' NOT LIKE %s "
                "ORDER BY created_at LIMIT %s FOR UPDATE",
                (
                    f"{_ENCRYPTED_PREFIX}%",
                    f"{_ENCRYPTED_PREFIX}%",
                    _BATCH_SIZE,
                ),
            ).fetchall()
            for row in rows:
                source_data = row["sources"]
                if isinstance(source_data, str) and source_data.startswith(
                        _ENCRYPTED_PREFIX):
                    encrypted_sources = source_data
                else:
                    if not isinstance(source_data, list):
                        raise ChatEncryptionUnavailableError(
                            "Legacy chat history sources are invalid")
                    encrypted_sources = encrypt_sources(source_data)
                content = row["content"]
                encrypted_content = (
                    content if content.startswith(_ENCRYPTED_PREFIX)
                    else encrypt_text(content)
                )
                conn.execute(
                    "UPDATE chat_messages SET content = %s, sources = %s::jsonb "
                    "WHERE id = %s",
                    (encrypted_content, json.dumps(encrypted_sources), row["id"]),
                )
        messages_encrypted += len(rows)
        if not rows:
            break

    return conversations_encrypted, messages_encrypted


def purge_expired_chat_history(conn) -> tuple[int, int]:
    """Expire message content and metadata after 180 days."""
    with conn.transaction():
        messages = conn.execute(
            "DELETE FROM chat_messages "
            "WHERE created_at < now() - (%s * interval '1 day')",
            (CHAT_HISTORY_RETENTION_DAYS,),
        )
        redacted_titles = conn.execute(
            "UPDATE chat_conversations SET title = %s "
            "WHERE created_at < now() - (%s * interval '1 day') "
            "AND title <> %s",
            (
                _REDACTED_TITLE,
                CHAT_HISTORY_RETENTION_DAYS,
                _REDACTED_TITLE,
            ),
        )
        conversations = conn.execute(
            "DELETE FROM chat_conversations "
            "WHERE updated_at < now() - (%s * interval '1 day')",
            (CHAT_HISTORY_RETENTION_DAYS,),
        )
    return (
        messages.rowcount,
        redacted_titles.rowcount,
        conversations.rowcount,
    )
