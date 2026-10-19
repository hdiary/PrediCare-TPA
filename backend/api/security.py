"""Hachage des mots de passe (bcrypt), jetons JWT et jetons de réinitialisation."""
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
import jwt

from api.config import get_settings


def _prep(password: str) -> bytes:
    # bcrypt ne lit que les 72 premiers octets
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prep(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prep(password), password_hash.encode("ascii"))
    except ValueError:
        return False


# Hash factice : permet de dépenser le même temps de calcul quand l'email
# n'existe pas, pour ne pas révéler quels comptes existent.
DUMMY_HASH = hash_password("dummy-password-for-timing")


def create_access_token(
    user_id: int,
    role: str,
    session_id: str | None = None,
) -> tuple[str, int]:
    """Retourne (jeton, durée en secondes).

    Le jeton ne contient que l'identifiant et le rôle ; le rôle réel est
    relu en base à chaque requête (voir deps.get_current_user).
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expires_in = settings.jwt_expire_minutes * 60
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "token_type": "access",
    }
    if session_id is not None:
        payload["sid"] = session_id
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def create_refresh_token(
    user_id: int,
    role: str,
    session_id: str,
    token_id: str | None = None,
) -> tuple[str, str, datetime]:
    """Return a refresh JWT, its unique identifier, and its expiration."""
    settings = get_settings()
    now = datetime.now(UTC)
    jti = token_id or str(uuid4())
    expires_at = now + timedelta(days=settings.jwt_refresh_expire_days)
    payload = {
        "sub": str(user_id),
        "role": role,
        "sid": session_id,
        "jti": jti,
        "token_type": "refresh",
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_token(token: str) -> dict:
    """Lève jwt.PyJWTError si le jeton est invalide ou expiré."""
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub"]},
    )


def generate_reset_token() -> tuple[str, str]:
    """Retourne (jeton à envoyer à l'utilisateur, empreinte SHA-256 à stocker).

    Le jeton est aléatoire (256 bits) : une empreinte simple suffit, contrairement à un mot
    de passe choisi par un humain.
    """
    token = secrets.token_urlsafe(32)
    return token, hash_reset_token(token)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
