"""Schémas de l'écran d'administration (seuil d'alerte et canaux de notification)."""
import re

from pydantic import BaseModel, Field, field_validator

RE_CANAL_SLACK = re.compile(r"^#?[a-z0-9][a-z0-9._-]{0,79}$")
RE_EMAIL = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


class SettingsModel(BaseModel):
    alert_threshold: float = Field(ge=0.0, le=1.0)
    slack_enabled: bool = False
    slack_channel: str = Field(default="", max_length=81)
    email_enabled: bool = False
    email_recipients: str = Field(default="", max_length=500)   # adresses séparées par des virgules

    @field_validator("slack_channel")
    @classmethod
    def _canal(cls, v: str) -> str:
        v = v.strip()
        if v and not RE_CANAL_SLACK.match(v):
            raise ValueError("Nom de canal Slack invalide (ex. #predicare-alertes)")
        return v

    @field_validator("email_recipients")
    @classmethod
    def _emails(cls, v: str) -> str:
        adresses = [a.strip() for a in v.split(",") if a.strip()]
        if len(adresses) > 10 or any(not RE_EMAIL.match(a) for a in adresses):
            raise ValueError("Adresses e-mail invalides (10 maximum, séparées par des virgules)")
        return ", ".join(adresses)


class AuditEntryOut(BaseModel):
    ts: str
    event_type: str
    actor: str
    entity: str
    model_version: str | None = None


class UserRowOut(BaseModel):
    user_id: int
    email: str
    role: str
    assure_id: str | None = None
    prestataire_id: str | None = None
    is_active: bool
    last_login: str | None = None
