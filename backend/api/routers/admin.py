"""Routes d'administration : seuil et canaux modifiables en direct, journal d'audit, modèle,
gestion des comptes utilisateurs.

À compléter : supervision détaillée et dérive.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query

from api import repositories as repo
from api.audit import write_audit, write_audit_compte
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
from api.schemas import Role
from api.schemas_admin import (
    AuditEntryOut,
    MessageOut,
    SettingsModel,
    StatutCompte,
    UserCreate,
    UserRowOut,
    UserUpdate,
    _controle_rattachement,
)
from api.security import generate_reset_token, hash_password
from api.services.mailer import send_reset_email
from api.services.model_registry import ModelUnavailableError, get_registry

router = APIRouter(prefix="/admin", tags=["admin"])
admin_only = Depends(require_role("administrateur"))


@router.get("/ping", dependencies=[admin_only])
def ping():
    """Sert à vérifier le contrôle d'accès par rôle."""
    return {"pong": True}


@router.get("/metrics", dependencies=[admin_only])
def get_admin_metrics(
    period: str = Query("24h", pattern="^(24h|7d|30d)$"),
    conn=Depends(get_db),
):
    interval = {"24h": "1 day", "7d": "7 days", "30d": "30 days"}[period]
    summary = conn.execute(
        """
        SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY latence_ms)
                 FILTER (WHERE latence_ms IS NOT NULL) AS latency_p95_ms
        FROM mv_bi_factures
        WHERE date_facture >= current_date - %s::interval
        """,
        (interval,),
    ).fetchone()
    series = conn.execute(
        """
        SELECT date_trunc('day', date_facture)::date AS day,
               percentile_cont(0.95) WITHIN GROUP (ORDER BY latence_ms)
                 FILTER (WHERE latence_ms IS NOT NULL) AS latency
        FROM mv_bi_factures
        WHERE date_facture >= current_date - %s::interval
        GROUP BY day ORDER BY day
        """,
        (interval,),
    ).fetchall()
    http = http_metrics.snapshot()
    uptime_minutes = max(http["uptime_s"] / 60, 1)
    return {
        "latency_p95_ms": summary["latency_p95_ms"],
        "requests_per_min": round(http["requetes_total"] / uptime_minutes, 2),
        "error_rate": (
            http["taux_erreur_5xx"] if http["requetes_total"] else None
        ),
        "drift_psi": None,
        "series": [
            {
                "date": row["day"].isoformat(),
                "latency": row["latency"],
            }
            for row in series
        ],
    }


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
    """Recharge la version portant l'alias actif dans MLflow (mise à jour ou retour arrière)."""
    previous = registry.get().version if registry.get() else None
    try:
        try:
            bundle = registry.load_active(conn, force=force)
        except TypeError:
            # Compatibility with the lightweight registry doubles used by API tests.
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


# ---------- gestion des comptes utilisateurs ----------

UserId = Path(ge=1, le=2_147_483_647, description="Identifiant du compte")


def _user_out(r: dict) -> dict:
    """Compte vu par l'API (jamais le hachage du mot de passe)."""
    return {
        "user_id": r["utilisateur_id"], "email": r["email"], "role": r["role"],
        "assure_id": r["assure_id"], "prestataire_id": r["prestataire_id"],
        "is_active": r["actif"],
        "last_login": r["derniere_connexion"].isoformat() if r["derniere_connexion"] else None,
    }


def _compte_ou_404(conn, user_id: int) -> dict:
    cible = repo.get_utilisateur(conn, user_id)
    if not cible:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    return cible


def _verifier_references(conn, assure_id: str | None, prestataire_id: str | None) -> None:
    if assure_id and not repo.assure_existe(conn, assure_id):
        raise HTTPException(status_code=422, detail="assure_id inconnu")
    if prestataire_id and not repo.prestataire_existe(conn, prestataire_id):
        raise HTTPException(status_code=422, detail="prestataire_id inconnu")


def _garde_fou_auto_blocage(admin: dict, cible: dict, *, role_final: str,
                            actif_final: bool) -> None:
    """Un administrateur ne peut ni se désactiver ni se rétrograder lui-même.

    Un autre administrateur peut toujours le faire : l'appelant est forcément actif."""
    if (cible["utilisateur_id"] == admin["user_id"]
            and (role_final != "administrateur" or not actif_final)):
        raise HTTPException(
            status_code=409,
            detail="Vous ne pouvez ni désactiver ni rétrograder votre propre compte",
        )


@router.get("/users", response_model=list[UserRowOut], dependencies=[admin_only])
def list_users(
    role: Role | None = None,
    statut: StatutCompte = "tous",
    q: str | None = Query(None, max_length=100, description="Recherche dans l'adresse e-mail"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn=Depends(get_db),
):
    """Comptes de la plateforme (jamais le hachage du mot de passe).

    `statut=inactifs` liste notamment les inscriptions en attente de validation.
    """
    actif = {"actifs": True, "inactifs": False, "tous": None}[statut]
    rows = repo.list_utilisateurs(conn, role=role, actif=actif, q=q, limit=limit, offset=offset)
    return [_user_out(r) for r in rows]


@router.get("/users/{user_id}", response_model=UserRowOut, dependencies=[admin_only])
def get_user(user_id: int = UserId, conn=Depends(get_db)):
    return _user_out(_compte_ou_404(conn, user_id))


@router.post("/users", response_model=UserRowOut, status_code=201)
def create_user(
    body: UserCreate,
    admin: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
):
    """Crée un compte (tout rôle). L'administrateur choisit le mot de passe initial."""
    _verifier_references(conn, body.assure_id, body.prestataire_id)
    created = repo.create_utilisateur(
        conn, email=body.email, password_hash=hash_password(body.password), role=body.role,
        assure_id=body.assure_id, prestataire_id=body.prestataire_id, actif=body.is_active,
    )
    if created is None:
        raise HTTPException(status_code=409, detail="Un compte existe déjà avec cette adresse")
    write_audit_compte(conn, event_type="compte_cree", actor_id=admin["user_id"],
                       entity_id=created["utilisateur_id"],
                       output_data={"role": body.role, "is_active": body.is_active})
    return _user_out(created)


@router.patch("/users/{user_id}", response_model=UserRowOut)
def update_user(
    body: UserUpdate,
    user_id: int = UserId,
    admin: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
):
    """Modifie le rôle, le rattachement ou l'état d'un compte (seuls les champs envoyés).

    Valider une inscription = PATCH `{"is_active": true, "assure_id": "ASS-..."}` (ou
    `prestataire_id`). Changer de rôle efface les rattachements non renvoyés.
    """
    cible = _compte_ou_404(conn, user_id)
    sent = body.model_fields_set
    role_final = body.role or cible["role"]
    role_change = role_final != cible["role"]
    assure_final = body.assure_id if "assure_id" in sent else (
        None if role_change else cible["assure_id"])
    presta_final = body.prestataire_id if "prestataire_id" in sent else (
        None if role_change else cible["prestataire_id"])
    actif_final = cible["actif"] if body.is_active is None else body.is_active

    if actif_final:   # un compte inactif (refusé, désactivé) peut rester non rattaché
        try:
            _controle_rattachement(role_final, assure_final, presta_final)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    _garde_fou_auto_blocage(admin, cible, role_final=role_final, actif_final=actif_final)
    _verifier_references(
        conn,
        assure_final if assure_final != cible["assure_id"] else None,
        presta_final if presta_final != cible["prestataire_id"] else None,
    )

    voulu = {"role": role_final, "assure_id": assure_final, "prestataire_id": presta_final,
             "actif": actif_final}
    champs = {k: v for k, v in voulu.items() if v != cible[k]}
    if not champs:
        return _user_out(cible)
    maj = repo.update_utilisateur(conn, user_id, champs)
    write_audit_compte(
        conn, event_type="compte_modifie", actor_id=admin["user_id"], entity_id=user_id,
        input_data={"champs": sorted(champs)},
        output_data={"role": maj["role"], "is_active": maj["actif"]},
    )
    return _user_out(maj)


@router.delete("/users/{user_id}", response_model=UserRowOut)
def deactivate_user(
    user_id: int = UserId,
    admin: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
):
    """Désactive un compte (aucune suppression : l'historique et l'audit restent cohérents).

    Effet immédiat : le rôle et l'état du compte sont relus en base à chaque requête.
    """
    cible = _compte_ou_404(conn, user_id)
    if not cible["actif"]:
        return _user_out(cible)
    _garde_fou_auto_blocage(admin, cible, role_final=cible["role"], actif_final=False)
    maj = repo.update_utilisateur(conn, user_id, {"actif": False})
    write_audit_compte(conn, event_type="compte_desactive", actor_id=admin["user_id"],
                       entity_id=user_id)
    return _user_out(maj)


@router.post("/users/{user_id}/unlock", response_model=UserRowOut)
def unlock_user(
    user_id: int = UserId,
    admin: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
):
    """Lève le verrouillage temporaire après trop d'échecs de connexion."""
    _compte_ou_404(conn, user_id)
    repo.deverrouiller_utilisateur(conn, user_id)
    write_audit_compte(conn, event_type="compte_deverrouille", actor_id=admin["user_id"],
                       entity_id=user_id)
    return _user_out(repo.get_utilisateur(conn, user_id))


@router.post("/users/{user_id}/reset-password", response_model=MessageOut, status_code=202)
def send_user_reset_link(
    background: BackgroundTasks,
    user_id: int = UserId,
    admin: dict = Depends(require_role("administrateur")),
    conn=Depends(get_db),
):
    """Envoie à l'utilisateur un lien de réinitialisation.

    L'administrateur ne voit jamais le jeton ni le mot de passe."""
    settings = get_settings()
    cible = _compte_ou_404(conn, user_id)
    if not cible["actif"]:
        raise HTTPException(status_code=409, detail="Compte inactif")
    recentes = repo.compter_demandes_reinitialisation(conn, user_id)
    if recentes >= settings.password_reset_max_per_hour:
        raise HTTPException(status_code=429,
                            detail="Trop de demandes de réinitialisation récentes")
    token, token_hash = generate_reset_token()
    repo.creer_jeton_reinitialisation(
        conn, user_id, token_hash, settings.password_reset_ttl_minutes)
    write_audit_compte(conn, event_type="mdp_reinitialisation_demandee",
                       actor_id=admin["user_id"], entity_id=user_id)
    conn.commit()   # le jeton doit exister avant que le lien soit envoyé
    background.add_task(send_reset_email, user_id, cible["email"], token)
    return MessageOut(detail="Lien de réinitialisation envoyé à l'utilisateur")
