from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from api.services import chat_security


class FakeResult:
    def __init__(self, rows=None, rowcount=0):
        self._rows = rows or []
        self.rowcount = rowcount

    def fetchall(self):
        return list(self._rows)


class FakeConnection:
    def __init__(self):
        self.conversations = [{
            "id": "conversation-1",
            "title": "Question personnelle",
        }]
        self.messages = [{
            "id": "message-1",
            "content": "Détail médical privé",
            "sources": [],
        }]
        self.statements = []

    def transaction(self):
        return nullcontext()

    def execute(self, statement, params=()):
        self.statements.append((statement, params))
        if statement.startswith("SELECT id, title"):
            return FakeResult([
                row for row in self.conversations
                if not row["title"].startswith(chat_security._ENCRYPTED_PREFIX)
            ])
        if statement.startswith("UPDATE chat_conversations SET title"):
            if "WHERE id = %s" not in statement:
                return FakeResult(rowcount=2)
            value, row_id = params
            next(row for row in self.conversations
                 if row["id"] == row_id)["title"] = value
            return FakeResult(rowcount=1)
        if statement.startswith("SELECT id, content, sources"):
            return FakeResult([
                row for row in self.messages
                if (not row["content"].startswith(
                    chat_security._ENCRYPTED_PREFIX)
                    or not isinstance(row["sources"], str)
                    or not row["sources"].startswith(
                        chat_security._ENCRYPTED_PREFIX))
            ])
        if statement.startswith("UPDATE chat_messages"):
            content, sources, row_id = params
            row = next(row for row in self.messages if row["id"] == row_id)
            row["content"] = content
            row["sources"] = sources.strip('"')
            return FakeResult(rowcount=1)
        if statement.startswith("DELETE FROM chat_messages"):
            return FakeResult(rowcount=3)
        if statement.startswith("DELETE FROM chat_conversations"):
            return FakeResult(rowcount=4)
        raise AssertionError(f"Unexpected SQL: {statement}")


@pytest.fixture
def chat_key(monkeypatch):
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(
        chat_security,
        "get_settings",
        lambda: SimpleNamespace(chat_encryption_key=key),
    )
    return key


def test_chat_text_and_sources_are_encrypted_at_rest(chat_key):
    text = "Question confidentielle"
    sources = [{"document": "contrat.pdf", "excerpt": "Garantie santé"}]

    encrypted_text = chat_security.encrypt_text(text)
    encrypted_sources = chat_security.encrypt_sources(sources)

    assert text not in encrypted_text
    assert "Garantie santé" not in encrypted_sources
    assert chat_security.decrypt_text(encrypted_text) == text
    assert chat_security.decrypt_sources(encrypted_sources) == sources


def test_missing_encryption_key_fails_closed(monkeypatch):
    monkeypatch.setattr(
        chat_security,
        "get_settings",
        lambda: SimpleNamespace(chat_encryption_key=None),
    )

    with pytest.raises(chat_security.ChatEncryptionUnavailableError):
        chat_security.encrypt_text("ne doit pas être stocké en clair")


def test_existing_plaintext_chat_rows_are_encrypted(chat_key):
    conn = FakeConnection()

    conversation_count, message_count = (
        chat_security.secure_existing_chat_history(conn))

    assert (conversation_count, message_count) == (1, 1)
    assert conn.conversations[0]["title"] != "Question personnelle"
    assert conn.messages[0]["content"] != "Détail médical privé"
    assert chat_security.decrypt_text(conn.conversations[0]["title"]) == (
        "Question personnelle")
    assert chat_security.decrypt_text(conn.messages[0]["content"]) == (
        "Détail médical privé")
    assert chat_security.decrypt_sources(conn.messages[0]["sources"]) == []


def test_retention_uses_180_day_cutoff_and_redacts_titles():
    conn = FakeConnection()

    counts = chat_security.purge_expired_chat_history(conn)

    assert counts == (3, 2, 4)
    assert len(conn.statements) == 3
    assert all(
        "interval '1 day'" in statement
        and chat_security.CHAT_HISTORY_RETENTION_DAYS in params
        for statement, params in conn.statements
    )
    assert "created_at" in conn.statements[0][0]
    assert "SET title" in conn.statements[1][0]
    assert "updated_at" in conn.statements[2][0]
