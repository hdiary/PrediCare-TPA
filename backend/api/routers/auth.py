"""Authentification : login (JSON et formulaire OAuth2) et profil."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from api.db import get_db
from api.deps import get_current_user
from api.schemas import LoginRequest, TokenResponse, UserOut
from api.security import DUMMY_HASH, create_access_token, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _authenticate(conn, email: str, password: str) -> dict:
    row = conn.execute(
        "SELECT user_id, email, password_hash, role, insured_id, provider_id, is_active "
        "FROM users WHERE email = %s",
        (email.strip().lower(),),
    ).fetchone()

    # Toujours vérifier un hash, même si l'utilisateur n'existe pas (anti-énumération)
    valid = verify_password(password, row["password_hash"] if row else DUMMY_HASH)
    if not row or not valid or not row["is_active"]:
        logger.warning("login_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
            headers={"WWW-Authenticate": "Bearer"},
        )

    conn.execute("UPDATE users SET last_login_at = now() WHERE user_id = %s", (row["user_id"],))
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
