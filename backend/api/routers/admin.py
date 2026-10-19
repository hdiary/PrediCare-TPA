"""Routes d'administration : seuil et canaux modifiables en direct, journal d'audit, modèle.

À compléter : supervision détaillée et dérive.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from api import repositories as repo
from api.audit import write_audit
from api.config import get_settings
from api.db import get_db
from api.deps import require_role
from api.schemas_admin import AuditEntryOut, SettingsModel, UserRowOut
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


# ---------- configuration modifiable sans toucher au code (CDC : « Configurable ») ----------

_CLES = ("seuil_alerte", "canal_slack_actif", "slack_canal", "canal_email_actif",
         "email_destinataires")


def _lire_settings(conn) -> SettingsModel:
    cfg = repo.get_configuration(conn, list(_CLES))
    try:
        seuil = float(cfg["seuil_alerte"])
    except (KeyError, ValueError):
        seuil = get_settings().alert_threshold
    return SettingsModel(
        alert_threshold=seuil,
        slack_enabled=cfg.get("canal_slack_actif") == "true",
        slack_channel=cfg.get("slack_canal", ""),
        email_enabled=cfg.get("canal_email_actif") == "true",
        email_recipients=cfg.get("email_destinataires", ""),
    )


@router.get("/settings", response_model=SettingsModel, dependencies=[admin_only])
def get_admin_settings(conn=Depends(get_db)):
    return _lire_settings(conn)


@router.put("/settings", response_model=SettingsModel)
def put_admin_settings(
    body: SettingsModel,
    user: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
):
    """Le nouveau seuil s'applique dès la prédiction suivante (relu en base à chaque appel)."""
    avant = _lire_settings(conn)
    repo.set_configuration(conn, {
        "seuil_alerte": repr(body.alert_threshold),
        "canal_slack_actif": "true" if body.slack_enabled else "false",
        "slack_canal": body.slack_channel,
        "canal_email_actif": "true" if body.email_enabled else "false",
        "email_destinataires": body.email_recipients,
    })
    write_audit(
        conn, event_type="config_modifiee", actor_id=user["user_id"], entity_type="configuration",
        entity_id="alertes", input_data=avant.model_dump(), output_data=body.model_dump(),
    )
    return body


# ---------- lecture du journal d'audit ----------

@router.get("/audit-log", response_model=list[AuditEntryOut], dependencies=[admin_only])
def get_audit_log(
    event_type: str | None = Query(None, max_length=40),
    limit: int = Query(100, ge=1, le=500),
    conn=Depends(get_db),
):
    """Pseudonymes uniquement : l'acteur est affiché sous la forme RÔLE-numéro."""
    out = []
    for r in repo.list_audit(conn, event_type=event_type, limit=limit):
        acteur = (
            f"{(r['role_acteur'] or 'SYSTEME').upper()}-{r['utilisateur_id']:04d}"
            if r["utilisateur_id"] is not None else "SYSTEME"
        )
        out.append({
            "ts": r["date"].isoformat(),
            "event_type": r["type_evenement"],
            "actor": acteur,
            "entity": f"{r['type_entite']} {r['entite_id'] or ''}".strip(),
            "model_version": r["version_modele"],
        })
    return out


@router.get("/users", response_model=list[UserRowOut], dependencies=[admin_only])
def list_users(conn=Depends(get_db)):
    """Comptes de la plateforme (jamais le hachage du mot de passe)."""
    return [
        {
            "user_id": r["utilisateur_id"], "email": r["email"], "role": r["role"],
            "assure_id": r["assure_id"], "prestataire_id": r["prestataire_id"],
            "is_active": r["actif"],
            "last_login": r["derniere_connexion"].isoformat() if r["derniere_connexion"] else None,
        }
        for r in repo.list_utilisateurs(conn)
    ]
