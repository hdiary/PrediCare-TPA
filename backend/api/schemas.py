"""Schémas Pydantic de l'authentification."""
import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

Role = Literal["professionnel_sante", "assure", "gestionnaire", "administrateur"]
# Rôles qu'une personne peut demander elle-même ; gestionnaire et administrateur
# ne sont créés que par un administrateur.
RoleInscription = Literal["professionnel_sante", "assure"]

RE_EMAIL = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


def _email(v: str) -> str:
    v = v.strip().lower()
    if len(v) > 254 or not RE_EMAIL.match(v):
        raise ValueError("Adresse e-mail invalide")
    return v


def _mot_de_passe(v: str) -> str:
    """Politique : 10 à 128 caractères, au moins une lettre et un chiffre."""
    if len(v) < 10:
        raise ValueError("Le mot de passe doit contenir au moins 10 caractères")
    if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Le mot de passe doit contenir au moins une lettre et un chiffre")
    return v


Email = Annotated[str, Field(min_length=3, max_length=254), AfterValidator(_email)]
NouveauMotDePasse = Annotated[str, Field(max_length=128), AfterValidator(_mot_de_passe)]


class RegisterRequest(BaseModel):
    email: Email
    password: NouveauMotDePasse
    role: RoleInscription


class ForgotPasswordRequest(BaseModel):
    email: Email


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: NouveauMotDePasse


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: NouveauMotDePasse


class MessageResponse(BaseModel):
    detail: str


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    user_id: int
    email: str
    role: Role
    assure_id: str | None = None
    prestataire_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # secondes
    refresh_expires_in: int  # secondes
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: Literal["ok", "degraded"]
    version: str
    uptime_s: int
    checks: dict[str, str]
    model_version: str | None = None
