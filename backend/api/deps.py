"""Dépendances d'authentification et d'autorisation."""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from uuid import UUID

from api.db import get_db
from api.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentification requise ou jeton invalide",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: str = Depends(oauth2_scheme), conn=Depends(get_db)) -> dict:
    """Utilisateur connecté, relu en base à chaque requête.

    Conséquence : désactiver un compte ou changer un rôle est effectif
    immédiatement, et assure_id vient de la base, jamais du client.
    """
    try:
        payload = decode_token(token)
        if payload.get("token_type", "access") != "access":
            raise jwt.InvalidTokenError("Not an access token")
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise _UNAUTHORIZED from None

    user = conn.execute(
        "SELECT utilisateur_id AS user_id, identifiant, email, role, assure_id, prestataire_id, "
        "actif AS is_active FROM utilisateurs WHERE utilisateur_id = %s",
        (user_id,),
    ).fetchone()
    if not user or not user["is_active"]:
        raise _UNAUTHORIZED
    session_id = payload.get("sid")
    if session_id is not None:
        try:
            if not isinstance(session_id, str):
                raise ValueError("Invalid session identifier")
            session_uuid = UUID(session_id)
            session = conn.execute(
                "SELECT 1 AS active FROM auth_sessions "
                "WHERE session_id = %s AND user_id = %s "
                "AND revoked_at IS NULL AND expires_at > now()",
                (session_uuid, user_id),
            ).fetchone()
        except (ValueError, TypeError, jwt.PyJWTError):
            raise _UNAUTHORIZED from None
        if not session:
            raise _UNAUTHORIZED
        user["session_id"] = session_id
    return user


def require_role(*roles: str):
    """Fabrique une dépendance qui n'autorise que les rôles listés.

    Exemple :
        @router.get("/alerts", dependencies=[Depends(require_role("gestionnaire"))])
    """

    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé pour ce rôle",
            )
        return user

    return checker
