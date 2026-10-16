"""Dépendances d'authentification et d'autorisation."""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from api.db import get_db
from api.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

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
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise _UNAUTHORIZED from None

    user = conn.execute(
        "SELECT utilisateur_id AS user_id, email, role, assure_id, prestataire_id, "
        "actif AS is_active FROM utilisateurs WHERE utilisateur_id = %s",
        (user_id,),
    ).fetchone()
    if not user or not user["is_active"]:
        raise _UNAUTHORIZED
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
