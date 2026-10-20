"""Tests de sécurité S1 (contrôle d'accès par rôle) et S12 (authentification).

S1  : RGPD art. 32, AI Act art. 15 - un assuré qui appelle un endpoint gestionnaire reçoit 403.
S12 : RGPD art. 32 - mots de passe hachés, session qui expire, échecs de connexion limités.
"""
from datetime import UTC, datetime, timedelta
from contextlib import nullcontext
from types import SimpleNamespace

import jwt
import pytest
from fastapi.testclient import TestClient

from api import bootstrap
from api.config import get_settings
from api.db import get_db
from api.main import app
from api.security import create_access_token, hash_password, verify_password
from api.services.model_registry import ModelUnavailableError, get_registry

PASSWORD = "Demo2026!"
EMAIL = "gestionnaire@predicare.local"

ROLES = {
    1: "professionnel_sante",
    2: "assure",
    3: "gestionnaire",
    4: "administrateur",
}


class Cur:
    def __init__(self, row=None, rows=None):
        self.row, self.rows = row, rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


# ======================= S1 : contrôle d'accès par rôle =======================

class RoleConn:
    """Ne connaît que la table des utilisateurs ; toute autre requête ne renvoie rien."""

    def execute(self, query, params=()):
        q = " ".join(query.split()).upper()
        if "FROM UTILISATEURS WHERE UTILISATEUR_ID" in q:
            return Cur(dict(user_id=params[0], email=f"u{params[0]}@x", role=ROLES[params[0]],
                            assure_id=None, prestataire_id=None, is_active=True))
        if q.startswith("SELECT COUNT(*)") and "FROM PREDICTIONS" in q:
            return Cur({"n": 0})
        return Cur(None)

    def commit(self):
        pass

    def transaction(self):
        return nullcontext()


class NoModelRegistry:
    last_error = None

    def get(self):
        return None

    def ensure_loaded(self):
        return None

    def load_active(self, force=False):
        raise ModelUnavailableError("indisponible (test)")

    def list_versions(self, conn):
        return []

    def current(self, conn):
        raise ModelUnavailableError("indisponible (test)")

    def metrics(self, conn):
        raise ModelUnavailableError("indisponible (test)")

    def activate_version(self, conn, version, user):
        raise ModelUnavailableError("indisponible (test)")


FID = "FAC-00000001"
# (méthode, chemin, corps JSON, rôles autorisés)
ENDPOINTS = [
    ("GET", "/alerts", None, {"gestionnaire", "administrateur"}),
    ("GET", "/api/v1/alerts", None, {"gestionnaire", "administrateur"}),
    ("GET", "/api/v1/alertes", None, {"gestionnaire", "administrateur"}),
    ("GET", f"/alerts/{FID}", None, {"gestionnaire", "administrateur"}),
    ("POST", f"/alerts/{FID}/decision", {"decision": "faux_positif"},
     {"gestionnaire", "administrateur"}),
    ("PATCH", f"/api/v1/alertes/{FID}/decision", {"decision": "REJETER"},
     {"gestionnaire", "administrateur"}),
    ("GET", f"/alerts/{FID}/identite", None, {"administrateur"}),
    ("GET", f"/api/v1/alerts/{FID}", None, {"gestionnaire", "administrateur"}),
    ("GET", "/api/v1/factures", None, {"professionnel_sante"}),
    ("GET", f"/api/v1/factures/{FID}", None, {"professionnel_sante"}),
    ("POST", "/predict", {}, {"administrateur", "professionnel_sante"}),
    ("GET", "/ordonnances/ORD-0000001/validite", None,
     {"administrateur", "professionnel_sante"}),
    ("GET", "/admin/ping", None, {"administrateur"}),
    ("GET", "/api/v1/admin/ping", None, {"administrateur"}),
    ("GET", "/admin/model", None, {"administrateur"}),
    ("POST", "/admin/model/reload", None, {"administrateur"}),
    ("GET", "/model/versions", None, {"administrateur"}),
    ("GET", "/model/current", None, {"administrateur"}),
    ("GET", "/model/metrics", None, {"administrateur"}),
    ("POST", "/model/activate/v1", None, {"administrateur"}),
    ("POST", "/model/rollback/v1", None, {"administrateur"}),
]


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = lambda: RoleConn()
    app.dependency_overrides[get_registry] = lambda: NoModelRegistry()
    yield TestClient(app)
    app.dependency_overrides.clear()


def bearer(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id, ROLES[user_id])[0]}"}


@pytest.mark.parametrize("method,path,body,allowed", ENDPOINTS)
def test_s1_insured_is_refused_on_every_staff_endpoint(client, method, path, body, allowed):
    """Cas du test S1 : un assuré appelle directement l'endpoint d'un écran gestionnaire."""
    r = client.request(method, path, json=body, headers=bearer(2))
    assert r.status_code == 403


@pytest.mark.parametrize("method,path,body,allowed", ENDPOINTS)
def test_s1_role_matrix(client, method, path, body, allowed):
    """Chaque rôle non autorisé reçoit 403 ; chaque rôle autorisé passe le contrôle d'accès."""
    for user_id, role in ROLES.items():
        r = client.request(method, path, json=body, headers=bearer(user_id))
        if role in allowed:
            assert r.status_code not in (401, 403), f"{role} bloqué sur {method} {path}"
        else:
            assert r.status_code == 403, f"{role} aurait dû être refusé sur {method} {path}"


@pytest.mark.parametrize("method,path,body,allowed", ENDPOINTS)
def test_s1_no_token_is_401(client, method, path, body, allowed):
    assert client.request(method, path, json=body).status_code == 401


def test_s1_role_in_token_cannot_be_forged(client):
    """Un jeton qui prétend « administrateur » mais appartient à l'assuré reste refusé :
    le rôle est relu en base, pas lu dans le jeton."""
    forged, _ = create_access_token(2, "administrateur")
    r = client.get("/admin/ping", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 403


# ======================= S12 : authentification =======================

# ---- mots de passe hachés ----

def test_s12_password_is_hashed_with_bcrypt_and_salted():
    h1, h2 = hash_password(PASSWORD), hash_password(PASSWORD)
    assert PASSWORD not in h1
    assert h1.startswith("$2")            # bcrypt
    assert h1 != h2                       # sel aléatoire
    assert verify_password(PASSWORD, h1)
    assert not verify_password("autre", h1)


def test_s12_demo_accounts_are_stored_hashed(monkeypatch):
    inserted = []

    class Conn:
        def execute(self, query, params=()):
            normalized = " ".join(query.split()).upper()
            if normalized.startswith("SELECT A.ASSURE_ID"):
                return Cur({"assure_id": "ASS-0000000001"})
            if normalized.startswith("SELECT P.PRESTATAIRE_ID"):
                return Cur({"prestataire_id": "PRE-00000001"})
            if normalized.startswith("INSERT INTO UTILISATEURS"):
                inserted.append(params)
                if "RETURNING UTILISATEUR_ID" in normalized:
                    return Cur({"utilisateur_id": 4})
            return Cur(None)

    class Pool:
        def connection(self, timeout=None):
            conn = Conn()

            class Ctx:
                def __enter__(self):
                    return conn

                def __exit__(self, *a):
                    return False

            return Ctx()

    monkeypatch.setattr(bootstrap, "get_pool", lambda: Pool())
    monkeypatch.setattr(
        bootstrap,
        "get_settings",
        lambda: SimpleNamespace(
            admin_email="admin@predicare.local",
            admin_initial_password=PASSWORD,
            demo_password=PASSWORD,
        ),
    )
    bootstrap.ensure_demo_users()

    assert len(inserted) == 4
    for _, stored, *_ in inserted:
        assert stored != PASSWORD and stored.startswith("$2")
    assert sum(len(params) == 2 for params in inserted) == 1


# ---- expiration de session ----

def test_s12_token_lifetime_matches_configuration():
    token, expires_in = create_access_token(3, "gestionnaire")
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["exp"] - claims["iat"] == get_settings().jwt_expire_minutes * 60 == expires_in


def test_s12_expired_session_is_refused(client):
    past = datetime.now(UTC) - timedelta(minutes=1)
    expired = jwt.encode({"sub": "3", "role": "gestionnaire", "exp": past},
                         get_settings().jwt_secret, algorithm="HS256")
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_s12_token_without_expiry_is_refused(client):
    eternal = jwt.encode({"sub": "3", "role": "gestionnaire"},
                         get_settings().jwt_secret, algorithm="HS256")
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {eternal}"})
    assert r.status_code == 401


# ---- échecs de connexion limités ----

class LoginConn:
    """Simule la table utilisateurs avec compteur d'échecs et verrouillage."""

    def __init__(self):
        self.hash = hash_password(PASSWORD)
        self.fails = 0
        self.locked = False

    def execute(self, query, params=()):
        q = " ".join(query.split()).upper()
        if q.startswith("SELECT") and "FROM UTILISATEURS WHERE EMAIL" in q:
            if params[0] != EMAIL:
                return Cur(None)
            return Cur(dict(user_id=3, email=EMAIL, password_hash=self.hash,
                            role="gestionnaire", assure_id=None, prestataire_id=None,
                            is_active=True, tentatives_echouees=self.fails,
                            verrouille=self.locked))
        if q.startswith("UPDATE UTILISATEURS SET TENTATIVES_ECHOUEES = CASE"):
            self.fails += 1
            if self.fails >= params[0]:
                self.locked, self.fails = True, 0
        elif "TENTATIVES_ECHOUEES = 0" in q:
            self.fails, self.locked = 0, False
        return Cur(None)

    def commit(self):
        pass


@pytest.fixture
def login_client():
    conn = LoginConn()
    app.dependency_overrides[get_db] = lambda: conn
    yield TestClient(app), conn
    app.dependency_overrides.clear()


def attempt(client, password):
    return client.post("/auth/login", json={"email": EMAIL, "password": password})


def test_s12_account_is_locked_after_max_failures(login_client):
    client, _ = login_client
    limit = get_settings().login_max_attempts
    for _ in range(limit):
        assert attempt(client, "mauvais").status_code == 401
    # Verrouillé : même le BON mot de passe est refusé, avec Retry-After
    r = attempt(client, PASSWORD)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) == get_settings().login_lockout_minutes * 60


def test_s12_success_resets_failure_counter(login_client):
    client, conn = login_client
    limit = get_settings().login_max_attempts
    for _ in range(limit - 1):
        assert attempt(client, "mauvais").status_code == 401
    assert attempt(client, PASSWORD).status_code == 200
    assert conn.fails == 0
    for _ in range(limit - 1):          # le compteur est reparti de zéro : pas de verrouillage
        assert attempt(client, "mauvais").status_code == 401
    assert attempt(client, PASSWORD).status_code == 200


def test_s12_unknown_email_gets_same_401_as_wrong_password(login_client):
    client, _ = login_client
    unknown = client.post("/auth/login", json={"email": "x@y.z", "password": "a"})
    wrong = attempt(client, "mauvais")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_s12_login_response_never_exposes_the_hash(login_client):
    client, _ = login_client
    body = attempt(client, PASSWORD).text.lower()
    assert "$2b$" not in body and "password_hash" not in body and "mot_de_passe" not in body
