"""Authentification : login (JSON et formulaire OAuth2) et profil.

Protection contre les tentatives répétées (S12) : après LOGIN_MAX_ATTEMPTS échecs
consécutifs, le compte est verrouillé LOGIN_LOCKOUT_MINUTES (HTTP 429). Un succès remet
le compteur à zéro. Limite : par compte (pas par adresse IP) ; un email inconnu n'est pas suivi.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from api.config import get_settings
from api.db import get_db
from api.deps import get_current_user
from api.schemas import LoginRequest, TokenResponse, UserOut
from api.security import DUMMY_HASH, create_access_token, verify_password

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


def _token_response(row: dict) -> TokenResponse:
    token, expires_in = create_access_token(row["user_id"], row["role"])
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserOut(**{k: row[k] for k in UserOut.model_fields}),
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, conn=Depends(get_db)):
    """Connexion JSON, utilisée par le frontend."""
    return _token_response(_authenticate(conn, body.email, body.password))


@router.post("/token", response_model=TokenResponse, include_in_schema=True)
def token(form: OAuth2PasswordRequestForm = Depends(), conn=Depends(get_db)):
    """Même chose en formulaire : fait fonctionner le bouton « Authorize » de /docs."""
    return _token_response(_authenticate(conn, form.username, form.password))


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(**{k: user[k] for k in UserOut.model_fields})
