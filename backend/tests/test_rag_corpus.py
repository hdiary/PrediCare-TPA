from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.db import get_db
from api.deps import get_current_user
from api.main import app
from api.routers import rag_corpus


class CorpusConn:
    def __init__(self):
        self.query = ""

    def execute(self, query, params=()):
        self.query = " ".join(query.split())
        return self

    def fetchall(self):
        return [{
            "id": 7,
            "filename": "Guide.pdf",
            "scope": "global",
            "contrat_id": None,
            "formule": None,
            "n_pages": 2,
            "ingested_at": datetime(2026, 10, 21, tzinfo=UTC),
            "chunks": 3,
        }]


def _manager():
    return {"user_id": 3, "role": "gestionnaire", "is_active": True}


def test_list_corpus_documents_requires_manager_and_returns_metadata(monkeypatch):
    conn = CorpusConn()
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: conn)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, _manager)

    response = TestClient(app).get("/rag-corpus")

    assert response.status_code == 200
    assert response.json()["items"][0]["filename"] == "Guide.pdf"
    assert "FROM rag_documents d LEFT JOIN rag_chunks" in conn.query


def test_add_contract_pdf_saves_and_indexes_in_contract_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_CORPUS_DIR", str(tmp_path))
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: CorpusConn())
    monkeypatch.setitem(app.dependency_overrides, get_current_user, _manager)
    monkeypatch.setattr(
        app.state,
        "rag_agent",
        SimpleNamespace(embeddings=object()),
        raising=False,
    )
    monkeypatch.setattr(app.state, "rag_ingestion_engine", object(), raising=False)
    calls = []

    def fake_ingest(path, contract_id, engine, embeddings, **kwargs):
        calls.append((path, contract_id, kwargs))
        return rag_corpus.IngestionResult(12, 5, False)

    monkeypatch.setattr(rag_corpus, "ingest_pdf", fake_ingest)
    response = TestClient(app).post(
        "/rag-corpus",
        files={"file": ("CP_CTR-000123.pdf", b"%PDF-1.7 contents", "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["scope"] == "contract"
    assert response.json()["contract_id"] == "CTR-000123"
    assert calls[0][0].parent.name == "conditions_particulieres"
    assert calls[0][0].read_bytes() == b"%PDF-1.7 contents"
    assert calls[0][1] == "CTR-000123"


def test_add_corpus_document_rejects_invalid_pdf(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_CORPUS_DIR", str(tmp_path))
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: CorpusConn())
    monkeypatch.setitem(app.dependency_overrides, get_current_user, _manager)
    response = TestClient(app).post(
        "/rag-corpus",
        files={"file": ("not-a-pdf.pdf", b"not a PDF", "application/pdf")},
    )

    assert response.status_code == 422
    assert list(tmp_path.iterdir()) == []


def test_provider_cannot_manage_rag_corpus(monkeypatch):
    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: {"user_id": 1, "role": "professionnel_sante", "is_active": True},
    )

    response = TestClient(app).get("/rag-corpus")

    assert response.status_code == 403
