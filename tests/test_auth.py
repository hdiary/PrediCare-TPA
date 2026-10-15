from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from api.config import get_settings
from api.db import get_db
from api.main import app
from api.security import create_access_token, hash_password, verify_password

PASSWORD = "Demo2026!"
USERS = {
    "gestionnaire@predicare.local": dict(user_id=3, role="gestionnaire", is_active=True),
    "admin@predicare.local": dict(user_id=4, role="administrateur", is_active=True),
    "off@predicare.local": dict(user_id=5, role="assure", is_active=False),
    "assure@predicare.local": dict(user_id=6, role="assure", is_active=True),
}


class FakeCursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConn:
    """Simule la table users : SELECT par email ou par user_id, UPDATE ignoré."""

    def __init__(self):
        self.hash = hash_password(PASSWORD)

    def _row(self, email, data):
        return {"email": email, "password_hash": self.hash, "insured_id": None,
                "provider_id": None, **data}

    def execute(self, query, params=()):
        q = query.strip().upper()
        if q.startswith("SELECT") and "WHERE EMAIL" in q:
            data = USERS.get(params[0])
            return FakeCursor(self._row(params[0], data) if data else None)
        if q.startswith("SELECT") and "WHERE USER_ID" in q:
            for email, data in USERS.items():
                if data["user_id"] == params[0]:
                    return FakeCursor(self._row(email, data))
            return FakeCursor(None)
        return FakeCursor(None)

    def commit(self):
        pass


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = lambda: FakeConn()
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client, email, password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_s1_assure_cannot_access_admin_endpoint(client):
    """S1 : un assuré authentifié reçoit un refus d'accès."""

    response_login = login(
        client,
        "assure@predicare.local",
    )

    assert response_login.status_code == 200

    token = response_login.json()["access_token"]

    response = client.get(
        "/admin/ping",
        headers=bearer(token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Accès refusé pour ce rôle"


def test_s12_password_is_hashed():
    """Le mot de passe ne doit pas être stocké en clair."""

    password = "MonMotDePasse2026!"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("MauvaisMotDePasse", password_hash)


def test_s12_expired_session_is_rejected(client):
    """Une session expirée ne permet plus d'accéder à l'API."""

    settings = get_settings()

    expired_at = datetime.now(UTC) - timedelta(hours=1)

    token = jwt.encode(
        {
            "sub": "3",
            "role": "gestionnaire",
            "exp": expired_at,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )

    response = client.get(
        "/auth/me",
        headers=bearer(token),
    )

    assert response.status_code == 401


def test_s12_failed_login_attempts_are_limited(client):
    """S12 : les tentatives répétées de connexion échouée sont limitées."""

    for _ in range(5):
        response = login(
            client,
            "gestionnaire@predicare.local",
            password="MotDePasseIncorrect",
        )
        assert response.status_code == 401

    response = login(
        client,
        "gestionnaire@predicare.local",
        password="MotDePasseIncorrect",
    )

    assert response.status_code == 429