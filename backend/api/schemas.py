"""Schémas Pydantic de l'authentification."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["professionnel_sante", "assure", "gestionnaire", "administrateur"]


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
