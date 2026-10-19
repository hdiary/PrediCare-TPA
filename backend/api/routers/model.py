"""Administrator-only model registry endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from api.db import get_db
from api.deps import require_role
from api.services.model_registry import ModelUnavailableError, get_registry

router = APIRouter(prefix="/model", tags=["model"])
admin_only = Depends(require_role("administrateur"))


@router.get("/versions", dependencies=[admin_only])
def list_model_versions(conn=Depends(get_db), registry=Depends(get_registry)):
    return {
        "actuelle": registry.get().version if registry.get() else None,
        "versions": registry.list_versions(conn),
    }


@router.get("/current", dependencies=[admin_only])
def current_model(conn=Depends(get_db), registry=Depends(get_registry)):
    try:
        return registry.current(conn)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Modèle indisponible") from exc


@router.get("/metrics", dependencies=[admin_only])
def model_metrics(conn=Depends(get_db), registry=Depends(get_registry)):
    try:
        return registry.metrics(conn)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Métriques du modèle indisponibles") from exc


@router.post("/activate/{version}", dependencies=[admin_only])
def activate_model(
    version: str,
    user: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
    registry=Depends(get_registry),
):
    try:
        bundle = registry.activate_version(conn, version, user)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=422, detail="Activation du modèle impossible") from exc
    return {"version": bundle.version, "sha256": bundle.sha256}


@router.post("/rollback/{version}", dependencies=[admin_only])
def rollback_model(
    version: str,
    user: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
    registry=Depends(get_registry),
):
    return activate_model(version, user, conn, registry)
