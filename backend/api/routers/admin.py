"""Routes d'administration (rôle administrateur uniquement).

- Seuil d'alerte modifiable en direct (P3-17) ; effet dès la prédiction suivante.
- Versions du modèle, activation et retour arrière (P3-17).
- Journal d'audit en lecture (P3-17).
- Métriques de supervision (P3-18) et dérive PSI (P3-19).
Toute modification est écrite dans le journal d'audit.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from api import repositories as repo
from api.audit import write_audit
from api.config import get_settings
from api.db import get_db
from api.deps import require_role
from api.schemas_admin import (
    ActivateRequest,
    AdminSettings,
    AdminSettingsPatch,
    AuditRow,
    ThresholdUpdate,
)
from api.services import config as config_service
from api.services import drift
from api.services.metrics import http_metrics
from api.services.model_registry import ModelUnavailableError, get_registry

router = APIRouter(prefix="/admin", tags=["admin"])
admin_only = Depends(require_role("administrateur"))


@router.get("/ping", dependencies=[admin_only])
def ping():
    """Sert à vérifier le contrôle d'accès par rôle."""
    return {"pong": True}


# ---------- application configuration ----------

@router.get("/settings", response_model=AdminSettings, dependencies=[admin_only])
@router.get("/config", response_model=AdminSettings, dependencies=[admin_only])
def get_admin_settings(conn=Depends(get_db)):
    return config_service.get_admin_settings(conn)


@router.put("/settings", response_model=AdminSettings)
def put_admin_settings(
    body: AdminSettings,
    user: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
):
    return config_service.update_admin_settings(conn, user, body)


@router.patch("/config", response_model=AdminSettings)
def patch_admin_config(
    body: AdminSettingsPatch,
    user: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
):
    settings = config_service.get_admin_settings(conn).model_dump()
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "channels":
            if value is None:
                raise HTTPException(
                    status_code=422,
                    detail="Une valeur de configuration ne peut pas être nulle",
                )
            for channel, channel_updates in value.items():
                if channel_updates is None:
                    raise HTTPException(
                        status_code=422,
                        detail="Une valeur de configuration ne peut pas être nulle",
                    )
                settings["channels"][channel].update(channel_updates)
        elif value is not None:
            settings[key] = value
        else:
            raise HTTPException(status_code=422, detail="Une valeur de configuration ne peut pas être nulle")
    try:
        validated = AdminSettings.model_validate(settings)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="Configuration invalide",
        ) from exc
    return config_service.update_admin_settings(conn, user, validated)


# ---------- seuil d'alerte ----------

@router.get("/threshold", dependencies=[admin_only])
def get_threshold(conn=Depends(get_db)):
    row = repo.get_config_row(conn, "seuil_alerte")
    if row:
        return {"seuil": float(row["valeur"]), "source": "configuration",
                "mis_a_jour_le": row["mis_a_jour_le"], "mis_a_jour_par": row["mis_a_jour_par"]}
    return {"seuil": get_settings().alert_threshold, "source": "defaut",
            "mis_a_jour_le": None, "mis_a_jour_par": None}


@router.put("/threshold")
def set_threshold(
    body: ThresholdUpdate,
    user: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
):
    """Modifie le seuil en direct : lu à chaque /predict, donc effectif immédiatement.

    Les prédictions déjà enregistrées gardent le seuil utilisé à leur création (`seuil_utilise`).
    """
    ancien = repo.get_seuil_alerte(conn, get_settings().alert_threshold)
    repo.set_config(conn, "seuil_alerte", repr(body.seuil), user["email"])
    write_audit(
        conn, event_type="seuil_modifie", actor_id=user["user_id"],
        entity_type="configuration", entity_id="seuil_alerte",
        input_data={"ancien_seuil": ancien, "nouveau_seuil": body.seuil},
        output_data={"seuil": body.seuil},
    )
    return {"seuil": body.seuil, "ancien_seuil": ancien}


# ---------- modèle : état, versions, activation, retour arrière ----------

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


@router.get("/model/versions", dependencies=[admin_only])
def model_versions(conn=Depends(get_db), registry=Depends(get_registry)):
    """Versions du modèle dans MLflow, alias et version actuellement chargée."""
    try:
        versions = registry.list_versions(conn)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"MLflow indisponible : {exc}") from exc
    bundle = registry.get()
    return {"actuelle": bundle.version if bundle else None, "versions": versions}


def _audit_model_change(conn, user, bundle, previous, action: str, extra: dict | None = None):
    write_audit(
        conn, event_type="modele_charge", actor_id=user["user_id"], entity_type="model",
        entity_id=bundle.name, model_name=bundle.name, model_version=bundle.version,
        input_data={"previous_version": previous, "action": action, **(extra or {})},
        output_data={"active_version": bundle.version},
    )


@router.post("/model/reload")
def model_reload(
    force: bool = False,
    user: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
    registry=Depends(get_registry),
):
    """Recharge la version portant l'alias actif dans MLflow."""
    previous = registry.get().version if registry.get() else None
    try:
        try:
            bundle = registry.load_active(conn, force=force)
        except TypeError:
            # Compatibility with the lightweight registry doubles used by API tests.
            bundle = registry.load_active(force=force)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"Chargement impossible : {exc}") from exc
    _audit_model_change(conn, user, bundle, previous, "reload", {"force": force})
    return {"name": bundle.name, "version": bundle.version, "previous_version": previous}


@router.post("/model/activate")
def model_activate(
    body: ActivateRequest,
    user: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
    registry=Depends(get_registry),
):
    """Active une version précise (déplace l'alias dans MLflow après chargement réussi)."""
    previous = registry.get().version if registry.get() else None
    try:
        bundle = registry.activate_version(conn, body.version, user)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"Activation impossible : {exc}") from exc
    _audit_model_change(conn, user, bundle, previous, "activate")
    return {"name": bundle.name, "version": bundle.version, "previous_version": previous}


@router.post("/model/rollback")
def model_rollback(
    user: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
    registry=Depends(get_registry),
):
    """Retour arrière : réactive la version qui précédait l'actuelle (d'après le journal d'audit)."""
    current = registry.get()
    if current is None:
        raise HTTPException(status_code=409, detail="Aucun modèle chargé")
    target = repo.rollback_target(conn, current.version)
    if target is None:
        raise HTTPException(
            status_code=409,
            detail="Aucune version précédente connue : utiliser POST /admin/model/activate")
    try:
        bundle = registry.activate_version(conn, target, user)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"Retour arrière impossible : {exc}") from exc
    _audit_model_change(conn, user, bundle, current.version, "rollback")
    return {"name": bundle.name, "version": bundle.version, "previous_version": current.version}


# ---------- journal d'audit (lecture seule) ----------

@router.get("/audit", response_model=list[AuditRow], dependencies=[admin_only])
def read_audit(
    type_evenement: str | None = Query(None, max_length=40, pattern=r"^[a-z_]+$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn=Depends(get_db),
):
    return repo.list_audit(conn, type_evenement, limit, offset)


# ---------- supervision ----------

@router.get("/metrics", dependencies=[admin_only])
def metrics(conn=Depends(get_db), registry=Depends(get_registry)):
    """Volume, erreurs et latence. `http` = processus courant ; `predictions` = base (24 h)."""
    preds = repo.metrics_predictions(conn, 24)
    audit = repo.metrics_audit_counts(conn, 24)
    volume = int(preds["volume"])
    bundle = registry.get()
    return {
        "http": http_metrics.snapshot(),
        "predictions_24h": {
            "volume": volume,
            "alertes": int(preds["alertes"]),
            "taux_alerte": round(int(preds["alertes"]) / volume, 4) if volume else 0.0,
            "latence_ms": {
                "p50": float(preds["p50"]) if preds["p50"] is not None else None,
                "p95": float(preds["p95"]) if preds["p95"] is not None else None,
                "max": preds["max_latence"],
            },
        },
        "evenements_24h": {
            "factures_rejetees": audit.get("facture_rejetee", 0),
            "erreurs_prediction": audit.get("erreur_prediction", 0),
            "decisions": audit.get("decision", 0),
        },
        "modele": {"charge": bundle is not None,
                   "version": bundle.version if bundle else None,
                   "derniere_erreur": registry.last_error},
    }


@router.get("/drift", dependencies=[admin_only])
def drift_status(conn=Depends(get_db)):
    """PSI par variable clé : référence = premières prédictions, courant = derniers jours."""
    s = get_settings()
    features = s.drift_feature_list
    if not features:
        importance = repo.recent_shap_importance(conn)
        features = [k for k, _ in sorted(importance.items(), key=lambda kv: -kv[1])[: s.drift_top_k]]
    reference = repo.drift_reference_variables(conn, s.drift_reference_size)
    current = repo.drift_current_variables(conn, s.drift_window_days, s.drift_reference_size)
    result = drift.compute_drift(reference, current, features, s.drift_min_samples)
    result["variables_suivies"] = features
    result["fenetre_jours"] = s.drift_window_days
    return result
