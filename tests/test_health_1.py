
from contextlib import contextmanager

from fastapi.testclient import TestClient

from api.main import app
from api.routers import health


class FakeConnection:
    def execute(self, query):
        assert query == "SELECT 1"


class FakePool:
    @contextmanager
    def connection(self, timeout=3):
        yield FakeConnection()


def test_health_database_available(monkeypatch):
    """S'assurer que /health retourne 200 lorsque la base est accessible."""
    monkeypatch.setattr(health, "get_pool", lambda: FakePool())

    response = TestClient(app).get("/health")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


def test_health_database_unavailable(monkeypatch):
    """S'assurer que /health retourne 503 lorsque la base est inaccessible."""

    class BrokenPool:
        @contextmanager
        def connection(self, timeout=3):
            raise RuntimeError("Database unavailable")
            yield  # Nécessaire pour que la fonction reste un générateur.

    monkeypatch.setattr(health, "get_pool", lambda: BrokenPool())

    response = TestClient(app).get("/health")

    assert response.status_code == 503

    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"].startswith("error:")