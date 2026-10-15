"""Schémas Pydantic de l'authentification."""
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["professionnel_sante", "assure", "gestionnaire", "administrateur"]


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    user_id: int
    email: str
    role: Role
    insured_id: str | None = None
    provider_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # secondes
    user: UserOut


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    uptime_s: int
    checks: dict[str, str]
