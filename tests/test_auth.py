from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest
from fastapi.testclient import TestClient

from api.config import get_settings
from api.db import get_db
from api.main import app
from api.security import create_access_token, hash_password, verify_password

PASSWORD = "Demo2026!"
USERS = {
    "gestionnaire@predicare.local": dict(
        user_id=3, identifiant="GES-123456789A", role="gestionnaire", is_active=True),
    "admin@predicare.local": dict(
        user_id=4, identifiant="ADM-123456789A", role="administrateur", is_active=True),
    "off@predicare.local": dict(
        user_id=5, identifiant="ASS-123456789A", role="assure", is_active=False),
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
        self.sessions = {}

    def _row(self, email, data):
        return {"email": email, "password_hash": self.hash, "assure_id": None,
                "prestataire_id": None, "tentatives_echouees": 0,
                "verrouille": False, **data}

    def execute(self, query, params=()):
        q = query.strip().upper()
        if q.startswith("INSERT INTO AUTH_SESSIONS"):
            session_id, user_id, refresh_jti, expires_at = params
            self.sessions[str(session_id)] = {
                "user_id": user_id,
                "refresh_jti": str(refresh_jti),
                "expires_at": expires_at,
                "revoked": False,
            }
            return FakeCursor({"session_id": session_id})
        if "FROM AUTH_SESSIONS" in q and "JOIN UTILISATEURS" in q:
            session_id, user_id, refresh_jti = params
            session = self.sessions.get(str(session_id))
            user_row = next(
                (
                    self._row(email, data)
                    for email, data in USERS.items()
                    if data["user_id"] == user_id
                ),
                None,
            )
            if (
                session
                and session["user_id"] == user_id
                and session["refresh_jti"] == str(refresh_jti)
                and not session["revoked"]
                and session["expires_at"] > datetime.now(UTC)
                and user_row
                and user_row["is_active"]
            ):
                return FakeCursor(user_row)
            return FakeCursor(None)
        if q.startswith("UPDATE AUTH_SESSIONS SET REFRESH_JTI"):
            refresh_jti, expires_at, session_id, user_id, previous_jti = params
            session = self.sessions.get(str(session_id))
            if (
                session
                and session["user_id"] == user_id
                and session["refresh_jti"] == str(previous_jti)
                and not session["revoked"]
            ):
                session["refresh_jti"] = str(refresh_jti)
                session["expires_at"] = expires_at
                return FakeCursor({"session_id": session_id})
            return FakeCursor(None)
        if q.startswith("UPDATE AUTH_SESSIONS SET REVOKED_AT"):
            if len(params) == 2:
                session_id, user_id = params
                session = self.sessions.get(str(session_id))
                if session and session["user_id"] == user_id:
                    session["revoked"] = True
            else:
                (user_id,) = params
                for session in self.sessions.values():
                    if session["user_id"] == user_id:
                        session["revoked"] = True
            return FakeCursor(None)
        if "FROM AUTH_SESSIONS" in q and "SELECT 1 AS ACTIVE" in q:
            session_id, user_id = params
            session = self.sessions.get(str(UUID(str(session_id))))
            return FakeCursor(
                {"active": 1}
                if session
                and session["user_id"] == user_id
                and not session["revoked"]
                and session["expires_at"] > datetime.now(UTC)
                else None
            )
        if q.startswith("SELECT") and "WHERE EMAIL" in q:
            account = next(
                ((email, data) for email, data in USERS.items()
                 if email == params[0] or data["identifiant"] == params[1]),
                None,
            )
            return FakeCursor(self._row(*account) if account else None)
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
    conn = FakeConn()
    app.dependency_overrides[get_db] = lambda: conn
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


def test_login_by_pseudonymous_identifier(client):
    response = client.post(
        "/auth/login",
        json={"identifier": "GES-123456789A", "password": PASSWORD},
    )
    assert response.status_code == 200
    assert response.json()["user"]["identifiant"] == "GES-123456789A"


def test_v1_login_alias_works(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "gestionnaire@predicare.local", "password": PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "gestionnaire"


def test_refresh_rotates_tokens_and_rejects_replay(client):
    initial = login(client, "gestionnaire@predicare.local").json()
    rotated = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial["refresh_token"]},
    )

    assert rotated.status_code == 200
    tokens = rotated.json()
    assert tokens["refresh_token"] != initial["refresh_token"]
    assert client.post(
        "/auth/refresh",
        json={"refresh_token": initial["refresh_token"]},
    ).status_code == 401
    assert client.get("/auth/me", headers=bearer(tokens["access_token"])).status_code == 200


def test_logout_revokes_access_and_refresh_tokens(client):
    tokens = login(client, "gestionnaire@predicare.local").json()

    response = client.post("/api/v1/auth/logout", headers=bearer(tokens["access_token"]))

    assert response.status_code == 204
    assert client.get("/auth/me", headers=bearer(tokens["access_token"])).status_code == 401
    assert client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    ).status_code == 401


def test_refresh_token_cannot_authenticate_protected_routes(client):
    tokens = login(client, "gestionnaire@predicare.local").json()
    assert client.get("/auth/me", headers=bearer(tokens["refresh_token"])).status_code == 401


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


def test_v1_routes_are_available_and_health_stays_at_root():
    paths = app.openapi()["paths"]

    assert "/health" in paths
    assert "/api/v1/health" not in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/refresh" in paths
    assert "/api/v1/auth/logout" in paths
    assert "/api/v1/predict" in paths
    assert "/api/v1/alerts" in paths
    assert "/api/v1/admin/metrics" in paths


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
