"""Authentification : login (JSON et formulaire OAuth2) et profil.

Protection contre les tentatives répétées (S12) : après LOGIN_MAX_ATTEMPTS échecs
consécutifs, le compte est verrouillé LOGIN_LOCKOUT_MINUTES (HTTP 429). Un succès remet
le compteur à zéro. Limite : par compte (pas par adresse IP) ; un email inconnu n'est pas suivi.
"""
import logging
from datetime import datetime
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from api.config import get_settings
from api.db import get_db
from api.deps import get_current_user
from api.schemas import LoginRequest, LogoutRequest, RefreshRequest, TokenResponse, UserOut
from api.security import (
    DUMMY_HASH,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _authenticate(conn, email: str, password: str) -> dict:
    settings = get_settings()
    row = conn.execute(
        "SELECT utilisateur_id AS user_id, email, mot_de_passe_hash AS password_hash, role, "
        "assure_id, prestataire_id, actif AS is_active, tentatives_echouees, "
        "(verrouille_jusqua IS NOT NULL AND verrouille_jusqua > now()) AS verrouille "
        "FROM utilisateurs WHERE email = %s",
        (email.strip().lower(),),
    ).fetchone()

    if row and row["verrouille"]:
        # Mot de passe non vérifié : un compte verrouillé ne sert pas d'oracle
        logger.warning("login_locked", extra={"user_id": row["user_id"]})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives échouées : compte temporairement verrouillé",
            headers={"Retry-After": str(settings.login_lockout_minutes * 60)},
        )

    # Toujours vérifier un hash, même si l'utilisateur n'existe pas (anti-énumération)
    valid = verify_password(password, row["password_hash"] if row else DUMMY_HASH)
    if not row or not valid or not row["is_active"]:
        if row:
            conn.execute(
                "UPDATE utilisateurs SET "
                "tentatives_echouees = CASE WHEN tentatives_echouees + 1 >= %s "
                "THEN 0 ELSE tentatives_echouees + 1 END, "
                "verrouille_jusqua = CASE WHEN tentatives_echouees + 1 >= %s "
                "THEN now() + make_interval(mins => %s) ELSE verrouille_jusqua END "
                "WHERE utilisateur_id = %s",
                (settings.login_max_attempts, settings.login_max_attempts,
                 settings.login_lockout_minutes, row["user_id"]),
            )
            conn.commit()  # l'échec doit être enregistré même si on lève l'erreur
        logger.warning("login_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
            headers={"WWW-Authenticate": "Bearer"},
        )

    conn.execute(
        "UPDATE utilisateurs SET derniere_connexion = now(), tentatives_echouees = 0, "
        "verrouille_jusqua = NULL WHERE utilisateur_id = %s",
        (row["user_id"],),
    )
    conn.commit()
    logger.info("login_ok", extra={"user_id": row["user_id"], "role": row["role"]})
    return row


def _token_response(
    row: dict,
    conn,
    *,
    session_id: str | None = None,
    previous_refresh_jti: str | None = None,
) -> TokenResponse:
    session_id = session_id or str(uuid4())
    refresh_token, refresh_jti, refresh_expires_at = create_refresh_token(
        row["user_id"], row["role"], session_id
    )
    if previous_refresh_jti is None:
        conn.execute(
            "INSERT INTO auth_sessions (session_id, user_id, refresh_jti, expires_at) "
            "VALUES (%s, %s, %s, %s)",
            (session_id, row["user_id"], refresh_jti, refresh_expires_at),
        )
    else:
        rotated = conn.execute(
            "UPDATE auth_sessions SET refresh_jti = %s, expires_at = %s "
            "WHERE session_id = %s AND user_id = %s AND refresh_jti = %s "
            "AND revoked_at IS NULL RETURNING session_id",
            (
                refresh_jti,
                refresh_expires_at,
                session_id,
                row["user_id"],
                previous_refresh_jti,
            ),
        ).fetchone()
        if rotated is None:
            raise _invalid_credentials()

    access_token, expires_in = create_access_token(
        row["user_id"], row["role"], session_id=session_id
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        refresh_expires_in=max(
            0, int((refresh_expires_at - datetime.now(refresh_expires_at.tzinfo)).total_seconds())
        ),
        user=UserOut(**{k: row[k] for k in UserOut.model_fields}),
    )


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Jeton de rafraîchissement invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, conn=Depends(get_db)):
    """Connexion JSON, utilisée par le frontend."""
    return _token_response(_authenticate(conn, body.email, body.password), conn)


@router.post("/token", response_model=TokenResponse, include_in_schema=True)
def token(form: OAuth2PasswordRequestForm = Depends(), conn=Depends(get_db)):
    """Même chose en formulaire : fait fonctionner le bouton « Authorize » de /docs."""
    return _token_response(_authenticate(conn, form.username, form.password), conn)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, conn=Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("token_type") != "refresh":
            raise jwt.InvalidTokenError("Not a refresh token")
        user_id = int(payload["sub"])
        if not isinstance(payload["sid"], str) or not isinstance(payload["jti"], str):
            raise jwt.InvalidTokenError("Invalid refresh claims")
        session_id = str(UUID(payload["sid"]))
        previous_jti = str(UUID(payload["jti"]))
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise _invalid_credentials() from None

    row = conn.execute(
        "SELECT u.utilisateur_id AS user_id, u.email, u.role, u.assure_id, u.prestataire_id "
        "FROM auth_sessions s JOIN utilisateurs u ON u.utilisateur_id = s.user_id "
        "WHERE s.session_id = %s AND s.user_id = %s AND s.refresh_jti = %s "
        "AND s.revoked_at IS NULL AND s.expires_at > now() AND u.actif = true "
        "FOR UPDATE OF s",
        (session_id, user_id, previous_jti),
    ).fetchone()
    if row is None:
        raise _invalid_credentials()
    return _token_response(
        row,
        conn,
        session_id=session_id,
        previous_refresh_jti=previous_jti,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    body: LogoutRequest | None = None,
    user: dict = Depends(get_current_user),
    conn=Depends(get_db),
):
    """Revoke this login session; legacy access tokens revoke all sessions."""
    session_id = user.get("session_id")
    if body and body.refresh_token:
        try:
            payload = decode_token(body.refresh_token)
            if (
                payload.get("token_type") != "refresh"
                or int(payload["sub"]) != user["user_id"]
                or not isinstance(payload["sid"], str)
            ):
                raise jwt.InvalidTokenError("Refresh token does not match user")
            refresh_session_id = str(UUID(payload["sid"]))
        except (jwt.PyJWTError, ValueError, KeyError, TypeError):
            raise _invalid_credentials() from None
        if session_id and refresh_session_id != session_id:
            raise _invalid_credentials()
        session_id = refresh_session_id

    if session_id:
        conn.execute(
            "UPDATE auth_sessions SET revoked_at = now() "
            "WHERE session_id = %s AND user_id = %s AND revoked_at IS NULL",
            (session_id, user["user_id"]),
        )
    else:
        conn.execute(
            "UPDATE auth_sessions SET revoked_at = now() "
            "WHERE user_id = %s AND revoked_at IS NULL",
            (user["user_id"],),
        )
    return None


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(**{k: user[k] for k in UserOut.model_fields})
