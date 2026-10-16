"""Routes d'administration (squelette).

À compléter : seuil d'alerte, supervision, dérive.
"""
from fastapi import APIRouter, Depends, HTTPException

from api.audit import write_audit
from api.db import get_db
from api.deps import require_role
from api.services.model_registry import ModelUnavailableError, get_registry

router = APIRouter(prefix="/admin", tags=["admin"])
admin_only = Depends(require_role("administrateur"))


@router.get("/ping", dependencies=[admin_only])
def ping():
    """Sert à vérifier le contrôle d'accès par rôle."""
    return {"pong": True}


@router.get("/model", dependencies=[admin_only])
def model_info(registry=Depends(get_registry)):
    bundle = registry.get()
    return {
        "loaded": bundle is not None,
        "name": bundle.name if bundle else None,
        "version": bundle.version if bundle else None,
        "loaded_at": bundle.loaded_at.isoformat() if bundle else None,
        "last_error": registry.last_error,
    }


@router.post("/model/reload")
def model_reload(
    force: bool = False,
    user: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
    registry=Depends(get_registry),
):
    """Recharge la version portant l'alias actif dans MLflow (mise à jour ou retour arrière)."""
    previous = registry.get().version if registry.get() else None
    try:
        bundle = registry.load_active(force=force)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"Chargement impossible : {exc}") from exc
    write_audit(
        conn, event_type="modele_charge", actor_id=user["user_id"], entity_type="model",
        entity_id=bundle.name, model_name=bundle.name, model_version=bundle.version,
        input_data={"previous_version": previous, "force": force},
        output_data={"active_version": bundle.version},
    )
    return {"name": bundle.name, "version": bundle.version, "previous_version": previous}
