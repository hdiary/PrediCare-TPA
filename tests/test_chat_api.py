from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.db import get_db
from api.deps import get_current_user
from api.main import app


class FakeConn:
    def __init__(self):
        self.calls = []
        self.owns_conversation = True

    def execute(self, query, params=()):
        query = str(query)
        self.calls.append((query, params))
        if "SELECT contrat_id FROM assures" in query:
            return FakeCursor({"contrat_id": "CTR-000048"})
        if "FROM prestataires" in query:
            return FakeCursor({"prestataire_id": params[0]})
        if "SELECT id FROM chat_conversations" in query:
            return FakeCursor({"id": params[0]} if self.owns_conversation else None)
        if "FROM chat_conversations c WHERE user_id" in query:
            return FakeCursor([])
        if "FROM chat_messages WHERE conversation_id" in query:
            return FakeCursor([])
        return FakeCursor(None)

    def transaction(self):
        return nullcontext()


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.row if isinstance(self.row, list) else []


class FakeAgent:
    def __init__(self):
        self.calls = []

    def answer(self, question, **kwargs):
        self.calls.append((question, kwargs))
        return SimpleNamespace(
            answer="Réponse factuelle.",
            sources=[
                SimpleNamespace(
                    filename="contrat.pdf",
                    article="Article 5",
                    page_start=3,
                    page_end=3,
                )
            ],
            blocked=False,
        )


@pytest.fixture
def chat_client(monkeypatch):
    user = {
        "user_id": 42,
        "role": "assure",
        "assure_id": "ASS-0123456789",
        "prestataire_id": None,
    }
    conn = FakeConn()
    agent = FakeAgent()
    app.dependency_overrides[get_db] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(app.state, "rag_agent", agent, raising=False)
    client = TestClient(app)
    yield client, conn, agent, user
    client.close()
    app.dependency_overrides.clear()


def test_chat_uses_authenticated_assured_and_returns_sources(chat_client):
    client, conn, agent, user = chat_client
    response = client.post("/chat", json={"message": "Quel est mon plafond ?"})

    assert response.status_code == 200
    result = response.json()
    assert result["answer"] == "Réponse factuelle."
    assert result["sources"] == [{
        "document": "contrat.pdf",
        "page": 3,
        "excerpt": "Article 5",
    }]
    assert agent.calls[0][1] == {
        "contract_id": "CTR-000048",
        "user_pseudo_id": user["assure_id"],
        "role": "assure",
        "assure_id": user["assure_id"],
        "prestataire_id": None,
    }
    assert any("INSERT INTO chat_conversations" in sql for sql, _ in conn.calls)
    assert any("INSERT INTO chat_messages" in sql for sql, _ in conn.calls)


def test_chat_rejects_client_supplied_identity_and_role(chat_client):
    client, _, agent, _ = chat_client
    response = client.post("/chat", json={
        "message": "Où en est mon dossier ?",
        "assure_id": "ASS-9999999999",
        "role": "professionnel_sante",
    })

    assert response.status_code == 422
    assert not agent.calls


def test_chat_rejects_conversation_owned_by_another_user(chat_client):
    client, conn, agent, _ = chat_client
    conn.owns_conversation = False
    response = client.post("/chat", json={
        "conversation_id": str(uuid4()),
        "message": "Question",
    })

    assert response.status_code == 404
    assert not agent.calls


def test_chat_history_is_scoped_to_authenticated_user(chat_client):
    client, conn, _, user = chat_client
    response = client.get("/chat/history")

    assert response.status_code == 200
    assert response.json() == {"conversations": []}
    query, params = next(
        (query, params) for query, params in conn.calls
        if "FROM chat_conversations c WHERE user_id" in query
    )
    assert "WHERE user_id = %s" in query
    assert params[0] == user["user_id"]


def test_chat_rejects_roles_without_chat_permission(chat_client):
    client, _, agent, user = chat_client
    user["role"] = "gestionnaire"
    response = client.post("/chat", json={"message": "Question"})

    assert response.status_code == 403
    assert not agent.calls


def test_chat_requires_authentication(chat_client):
    client, _, _, _ = chat_client
    app.dependency_overrides.pop(get_current_user)

    response = client.post("/chat", json={"message": "Question"})

    assert response.status_code == 401


def test_provider_chat_uses_only_server_side_provider_identity(chat_client):
    client, conn, agent, user = chat_client
    user.update({
        "role": "professionnel_sante",
        "assure_id": None,
        "prestataire_id": "PRE-00123",
    })
    response = client.post("/chat", json={
        "message": "Où en est ma facture ?",
        "assure_id": "ASS-9999999999",
    })

    assert response.status_code == 422
    response = client.post("/chat", json={"message": "Où en est ma facture ?"})
    assert response.status_code == 200
    assert agent.calls[0][1] == {
        "contract_id": None,
        "user_pseudo_id": user["prestataire_id"],
        "role": "professionnel_sante",
        "assure_id": None,
        "prestataire_id": user["prestataire_id"],
    }
    assert not any("SELECT contrat_id FROM assures" in sql for sql, _ in conn.calls)
