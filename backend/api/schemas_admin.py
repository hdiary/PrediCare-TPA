"""Schémas de l'écran d'administration (seuil d'alerte et canaux de notification)."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.schemas import Email


class AuditEntryOut(BaseModel):
    ts: str
    event_type: str
    actor: str
    entity: str
    model_version: str | None = None


class MessageOut(BaseModel):
    detail: str


class SettingsModel(BaseModel):
    alert_threshold: float = Field(gt=0, lt=1)
    slack_enabled: bool
    slack_channel: str
    email_enabled: bool
    email_recipients: str


StatutCompte = Literal["actifs", "inactifs", "tous"]


class UserCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=100)
    prenoms: str = Field(min_length=1, max_length=150)
    sexe: Literal["F", "M"]
    date_naissance: date
    telephone: str = Field(min_length=3, max_length=30)
    email: Email | None = None
    adresse: str = Field(min_length=1, max_length=255)
    ville: str = Field(min_length=1, max_length=100)
    numero_cin: str | None = Field(default=None, pattern=r"^\d{12}$")
    role: Literal["professionnel_sante", "assure", "gestionnaire", "administrateur"]
    assure_id: str | None = None
    prestataire_id: str | None = None

    @field_validator("date_naissance")
    @classmethod
    def date_is_not_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("La date de naissance ne peut pas être dans le futur")
        return value


class UserUpdate(BaseModel):
    role: Literal["professionnel_sante", "assure", "gestionnaire", "administrateur"] | None = None
    assure_id: str | None = None
    prestataire_id: str | None = None
    is_active: bool | None = None


class UserRowOut(BaseModel):
    user_id: int
    identifiant: str | None = None
    email: str | None = None
    role: str
    assure_id: str | None = None
    prestataire_id: str | None = None
    is_active: bool
    last_login: str | None = None


class UserPageOut(BaseModel):
    items: list[UserRowOut]
    total: int


class UserCreatedOut(UserRowOut):
    mot_de_passe_provisoire: str
    email_envoye: bool


def _controle_rattachement(role: str, assure_id: str | None, prestataire_id: str | None) -> None:
    if role == "assure" and not assure_id:
        raise ValueError("Un compte assure doit être rattaché à un assuré")
    if role == "professionnel_sante" and not prestataire_id:
        raise ValueError("Un compte professionnel_sante doit être rattaché à un prestataire")
    if role != "assure" and assure_id:
        raise ValueError("Seul un compte assure peut être rattaché à un assuré")
    if role != "professionnel_sante" and prestataire_id:
        raise ValueError("Seul un compte professionnel_sante peut être rattaché à un prestataire")


class ThresholdUpdate(BaseModel):
    seuil: float = Field(gt=0, lt=1, description="Score minimal (exclu 0 et 1) déclenchant une alerte")


class SlackChannelSettings(BaseModel):
    enabled: bool
    channel: str = Field(pattern=r"^#[a-z0-9-]{1,80}$")


class EmailChannelSettings(BaseModel):
    enabled: bool
    address: str = Field(
        min_length=3,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )


class NotificationChannelSettings(BaseModel):
    slack: SlackChannelSettings
    email: EmailChannelSettings


class AdminSettings(BaseModel):
    alert_threshold: float = Field(gt=0, lt=1)
    extended_rule_enabled: bool
    channels: NotificationChannelSettings


class SlackChannelSettingsPatch(BaseModel):
    enabled: bool | None = None
    channel: str | None = Field(default=None, pattern=r"^#[a-z0-9-]{1,80}$")


class EmailChannelSettingsPatch(BaseModel):
    enabled: bool | None = None
    address: str | None = Field(
        default=None,
        min_length=3,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )


class NotificationChannelSettingsPatch(BaseModel):
    slack: SlackChannelSettingsPatch | None = None
    email: EmailChannelSettingsPatch | None = None


class AdminSettingsPatch(BaseModel):
    alert_threshold: float | None = Field(default=None, gt=0, lt=1)
    extended_rule_enabled: bool | None = None
    channels: NotificationChannelSettingsPatch | None = None


class ActivateRequest(BaseModel):
    version: str = Field(pattern=r"^\d{1,6}$", description="Numéro de version MLflow")


class KpiJour(BaseModel):
    jour: date
    factures: int
    alertes: int


class KpiRegle(BaseModel):
    regle_code: str
    n: int


class KpiResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    periode_jours: int
    factures_scorees: int
    taux_alerte: float
    alertes_total: int
    alertes_en_attente: int
    alertes_traitees: int
    fraudes_confirmees: int
    faux_positifs: int
    a_investiguer: int
    precision: float | None = Field(
        None, description="fraudes confirmées / (fraudes confirmées + faux positifs)")
    montant_en_attente: int = Field(description="MGA, alertes sans décision")
    montant_fraude_confirmee: int = Field(description="MGA, factures dont la fraude est confirmée")
    montant_economise: int = Field(description="MGA, saisi par les gestionnaires")
    score_moyen: float
    par_jour: list[KpiJour]
    regles: list[KpiRegle]


class RegleAlerte(BaseModel):
    alerte_regle_id: int | None = None
    regle_code: str
    severite: str
    message: str
    details: dict | None = None
    cree_le: datetime | None = None


class AuditRow(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    audit_id: int
    horodatage: datetime
    type_evenement: str
    utilisateur_id: int | None = None
    type_entite: str
    entite_id: str | None = None
    nom_modele: str | None = None
    version_modele: str | None = None
    entree: dict | None = None
    sortie: dict | None = None
