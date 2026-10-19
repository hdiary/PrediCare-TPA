"""Schémas de l'écran d'administration (seuil d'alerte et canaux de notification)."""
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from api.schemas import Email, NouveauMotDePasse, Role

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


# ---------- gestion des comptes par l'administrateur ----------

class UserCreate(BaseModel):
    """Création d'un compte par un administrateur (actif d'emblée par défaut)."""
    email: Email
    password: NouveauMotDePasse
    role: Role
    assure_id: str | None = Field(default=None, pattern=r"^ASS-[0-9A-F]{10}$")
    prestataire_id: str | None = Field(default=None, pattern=r"^PRE-\d{5}$")
    is_active: bool = True

    @model_validator(mode="after")
    def _rattachement(self):
        _controle_rattachement(self.role, self.assure_id, self.prestataire_id)
        return self


class UserUpdate(BaseModel):
    """Modification partielle : seuls les champs envoyés changent (null efface un rattachement)."""
    role: Role | None = None
    assure_id: str | None = Field(default=None, pattern=r"^ASS-[0-9A-F]{10}$")
    prestataire_id: str | None = Field(default=None, pattern=r"^PRE-\d{5}$")
    is_active: bool | None = None


def _controle_rattachement(role: str, assure_id: str | None, prestataire_id: str | None) -> None:
    """Un assuré est lié à un assuré, un professionnel à un prestataire, les autres à rien."""
    if role == "assure" and (assure_id is None or prestataire_id is not None):
        raise ValueError("Un compte assuré exige assure_id (et pas de prestataire_id)")
    if role == "professionnel_sante" and (prestataire_id is None or assure_id is not None):
        raise ValueError("Un compte professionnel exige prestataire_id (et pas d'assure_id)")
    if role in ("gestionnaire", "administrateur") and (assure_id or prestataire_id):
        raise ValueError("Ce rôle n'est rattaché ni à un assuré ni à un prestataire")


class MessageOut(BaseModel):
    detail: str


StatutCompte = Literal["actifs", "inactifs", "tous"]
