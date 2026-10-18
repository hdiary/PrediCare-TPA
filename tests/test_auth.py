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
        return {"email": email, "password_hash": self.hash, "assure_id": None,
                "prestataire_id": None, "tentatives_echouees": 0,
                "verrouille": False, **data}

    def execute(self, query, params=()):
        q = query.strip().upper()
        if q.startswith("SELECT") and "WHERE EMAIL" in q:
            data = USERS.get(params[0])
            return FakeCursor(self._row(params[0], data) if data else None)
        if q.startswith("SELECT") and "WHERE UTILISATEUR_ID" in q:
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


def test_password_hash_roundtrip():
    h = hash_password("secret")
    assert verify_password("secret", h)
    assert not verify_password("autre", h)


def test_login_success(client):
    r = login(client, "gestionnaire@predicare.local")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "gestionnaire"
    payload = jwt.decode(body["access_token"], get_settings().jwt_secret, algorithms=["HS256"])
    assert payload["sub"] == "3"


def test_login_email_is_case_insensitive(client):
    assert login(client, "  Gestionnaire@PrediCare.local ").status_code == 200


@pytest.mark.parametrize(
    "email,password",
    [
        ("gestionnaire@predicare.local", "mauvais"),
        ("inconnu@predicare.local", PASSWORD),
        ("off@predicare.local", PASSWORD),  # compte désactivé
    ],
)
def test_login_failure_is_generic_401(client, email, password):
    r = login(client, email, password)
    assert r.status_code == 401
    assert r.json()["detail"] == "Identifiants invalides"


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_token(client):
    token = login(client, "gestionnaire@predicare.local").json()["access_token"]
    r = client.get("/auth/me", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["email"] == "gestionnaire@predicare.local"


def test_expired_token_rejected(client):
    s = get_settings()
    past = datetime.now(UTC) - timedelta(hours=1)
    token = jwt.encode(
        {"sub": "3", "role": "gestionnaire", "exp": past}, s.jwt_secret, algorithm="HS256"
    )
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401


def test_token_signed_with_other_key_rejected(client):
    token = jwt.encode({"sub": "3", "exp": datetime.now(UTC) + timedelta(hours=1)},
                       "mauvaise-cle" * 4, algorithm="HS256")
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401


def test_deactivated_user_with_valid_token_rejected(client):
    token, _ = create_access_token(5, "assure")
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401


def test_role_enforcement(client):
    manager = login(client, "gestionnaire@predicare.local").json()["access_token"]
    admin = login(client, "admin@predicare.local").json()["access_token"]
    assert client.get("/admin/ping", headers=bearer(manager)).status_code == 403
    assert client.get("/admin/ping", headers=bearer(admin)).status_code == 200
    assert client.get("/admin/ping").status_code == 401


def test_health_degraded_without_database():
    # Pas de lifespan => pas de pool => 503 propre, sans exception
    r = TestClient(app).get("/health")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
