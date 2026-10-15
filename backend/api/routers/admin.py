"""Routes d'administration (squelette).

Ajouter ici : seuil d'alerte, versions du modèle, supervision, dérive.
"""
from fastapi import APIRouter, Depends

from api.deps import require_role

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role("administrateur"))],
)


@router.get("/ping")
def ping():
    """Sert à vérifier le contrôle d'accès par rôle."""
    return {"pong": True}
