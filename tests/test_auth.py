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
    """Simule la table users avec état persistant (failed_attempts / locked_until)."""

    MAX_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15

    def __init__(self):
        self.hash = hash_password(PASSWORD)
        # état mutable par user_id
        self.state = {
            data["user_id"]: {"failed_attempts": 0, "locked_until": None}
            for data in USERS.values()
        }

    def _row(self, email, data):
        st = self.state[data["user_id"]]
        now = datetime.now(UTC)
        locked_until = st["locked_until"]
        is_locked = locked_until is not None and locked_until > now
        lock_expired = locked_until is not None and locked_until <= now
        return {
            "email": email,
            "password_hash": self.hash,
            "insured_id": None,
            "provider_id": None,
            "failed_attempts": st["failed_attempts"],
            "locked_until": locked_until,
            "is_locked": is_locked,
            "lock_expired": lock_expired,
            **data,
        }

    def execute(self, query, params=()):
        q = " ".join(query.split()).upper()

        if q.startswith("SELECT") and "WHERE EMAIL" in q:
            data = USERS.get(params[0])
            return FakeCursor(self._row(params[0], data) if data else None)

        if q.startswith("SELECT") and "WHERE USER_ID" in q:
            for email, data in USERS.items():
                if data["user_id"] == params[0]:
                    return FakeCursor(self._row(email, data))
            return FakeCursor(None)

        # UPDATE ... SET failed_attempts = 0, locked_until = NULL (reset expiration)
        if q.startswith("UPDATE") and "SET FAILED_ATTEMPTS = 0, LOCKED_UNTIL = NULL" in q:
            user_id = params[0]
            self.state[user_id]["failed_attempts"] = 0
            self.state[user_id]["locked_until"] = None
            return FakeCursor(None)

        # UPDATE ... SET last_login_at = now(), failed_attempts = 0, locked_until = NULL
        if q.startswith("UPDATE") and "LAST_LOGIN_AT = NOW()" in q:
            user_id = params[0]
            self.state[user_id]["failed_attempts"] = 0
            self.state[user_id]["locked_until"] = None
            return FakeCursor(None)

        # UPDATE d'échec : failed_attempts = CASE ... + locked_until = CASE ...
        if q.startswith("UPDATE") and "FAILED_ATTEMPTS + 1" in q:
            # params = (False, False, MAX_ATTEMPTS, LOCKOUT_DURATION_MINUTES, user_id)
            max_attempts = params[2]
            lockout_minutes = params[3]
            user_id = params[4]
            st = self.state[user_id]
            st["failed_attempts"] += 1
            if st["failed_attempts"] >= max_attempts:
                st["locked_until"] = datetime.now(UTC) + timedelta(minutes=lockout_minutes)
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


