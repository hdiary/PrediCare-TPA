"""Authentification : login (JSON et formulaire OAuth2), profil, inscription, mot de passe.

Protection contre les tentatives répétées (S12) : après LOGIN_MAX_ATTEMPTS échecs
consécutifs, le compte est verrouillé LOGIN_LOCKOUT_MINUTES (HTTP 429). Un succès remet
le compteur à zéro. Limite : par compte (pas par adresse IP) ; un email inconnu n'est pas suivi.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from api import repositories as repo
from api.audit import write_audit_compte
from api.config import get_settings
from api.db import get_db
from api.deps import get_current_user
from api.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from api.security import (
    DUMMY_HASH,
    create_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from api.services.mailer import send_reset_email

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
    if row and valid and not row["is_active"]:
        # Mot de passe correct : on peut dire pourquoi la connexion est refusée (compte en
        # attente de validation après inscription, ou désactivé). Aucun compteur d'échecs.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte inactif ou en attente de validation par un administrateur",
        )
    if not row or not valid:
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
    if len(form.username) > 254 or len(form.password) > 128:   # mêmes bornes que LoginRequest
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _token_response(_authenticate(conn, form.username, form.password))


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(**{k: user[k] for k in UserOut.model_fields})


# ---------- inscription, mot de passe oublié, changement de mot de passe ----------

@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
def register(body: RegisterRequest, conn=Depends(get_db)):
    """Demande de compte (assuré ou professionnel de santé).

    Le compte est créé INACTIF et sans rattachement : un administrateur doit le valider et le
    lier à l'assuré ou au prestataire (PATCH /admin/users/{id}). Le rattachement n'est jamais
    pris dans la requête. La réponse est identique si l'adresse existe déjà (pas d'énumération
    de comptes).
    """
    if not get_settings().registration_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Les inscriptions sont désactivées")
    # Le hachage est toujours calculé : même durée que l'adresse existe ou non
    password_hash = hash_password(body.password)
    created = repo.create_utilisateur(
        conn, email=body.email, password_hash=password_hash, role=body.role,
        assure_id=None, prestataire_id=None, actif=False,
    )
    if created:
        write_audit_compte(conn, event_type="compte_demande", actor_id=None,
                           entity_id=created["utilisateur_id"], output_data={"role": body.role})
        logger.info("register_ok", extra={"user_id": created["utilisateur_id"],
                                          "role": body.role})
    return MessageResponse(
        detail="Demande enregistrée. Un administrateur doit valider votre compte "
               "avant votre première connexion."
    )


@router.post("/forgot-password", response_model=MessageResponse,
             status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: ForgotPasswordRequest, background: BackgroundTasks,
                    conn=Depends(get_db)):
    """Envoie un lien de réinitialisation par e-mail (usage unique, durée limitée).

    Réponse toujours identique : on ne révèle pas si l'adresse correspond à un compte. L'envoi
    se fait après la réponse. Limite : PASSWORD_RESET_MAX_PER_HOUR demandes par compte et par
    heure. Les anciens liens du compte sont invalidés à chaque nouvelle demande.
    """
    settings = get_settings()
    user = repo.get_utilisateur_par_email(conn, body.email)
    if user and user["actif"]:
        user_id = user["utilisateur_id"]
        if repo.compter_demandes_reinitialisation(conn, user_id) >= \
                settings.password_reset_max_per_hour:
            logger.warning("password_reset_rate_limited", extra={"user_id": user_id})
        else:
            token, token_hash = generate_reset_token()
            repo.creer_jeton_reinitialisation(
                conn, user_id, token_hash, settings.password_reset_ttl_minutes)
            write_audit_compte(conn, event_type="mdp_reinitialisation_demandee",
                               actor_id=user_id, entity_id=user_id)
            conn.commit()   # le jeton doit exister avant que le lien soit envoyé
            background.add_task(send_reset_email, user_id, user["email"], token)
    return MessageResponse(
        detail="Si cette adresse correspond à un compte actif, un e-mail de "
               "réinitialisation vient d'être envoyé."
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest, conn=Depends(get_db)):
    """Définit un nouveau mot de passe à partir du lien reçu par e-mail (usage unique)."""
    invalide = HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                             detail="Lien invalide ou expiré")
    user_id = repo.consommer_jeton_reinitialisation(conn, hash_reset_token(body.token))
    if user_id is None:
        raise invalide
    user = repo.get_utilisateur(conn, user_id)
    if not user or not user["actif"]:
        raise invalide   # annule aussi la consommation du jeton (transaction non validée)
    repo.set_mot_de_passe(conn, user_id, hash_password(body.new_password))
    repo.invalider_jetons_reinitialisation(conn, user_id)
    write_audit_compte(conn, event_type="mdp_reinitialise", actor_id=user_id, entity_id=user_id)
    logger.info("password_reset_ok", extra={"user_id": user_id})
    return MessageResponse(detail="Mot de passe mis à jour. Vous pouvez vous connecter.")


@router.post("/change-password", response_model=MessageResponse)
def change_password(body: ChangePasswordRequest, user: dict = Depends(get_current_user),
                    conn=Depends(get_db)):
    """Changement du mot de passe par l'utilisateur connecté (ancien mot de passe requis).

    Les échecs alimentent le même verrouillage que la connexion, pour qu'un jeton volé ne
    permette pas de deviner l'ancien mot de passe sans limite.
    """
    settings = get_settings()
    user_id = user["user_id"]
    if repo.est_verrouille(conn, user_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives échouées : compte temporairement verrouillé",
            headers={"Retry-After": str(settings.login_lockout_minutes * 60)},
        )
    current_hash = repo.get_mot_de_passe_hash(conn, user_id)
    if not current_hash or not verify_password(body.current_password, current_hash):
        repo.enregistrer_echec_mot_de_passe(
            conn, user_id, settings.login_max_attempts, settings.login_lockout_minutes)
        conn.commit()   # l'échec doit être enregistré même si on lève l'erreur
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Mot de passe actuel incorrect")
    if verify_password(body.new_password, current_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Le nouveau mot de passe doit être différent de l'ancien")
    repo.set_mot_de_passe(conn, user_id, hash_password(body.new_password))
    repo.invalider_jetons_reinitialisation(conn, user_id)
    write_audit_compte(conn, event_type="mdp_modifie", actor_id=user_id, entity_id=user_id)
    return MessageResponse(detail="Mot de passe modifié.")
