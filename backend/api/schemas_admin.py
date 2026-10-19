"""Schémas des endpoints d'administration, de KPI et de supervision."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


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
