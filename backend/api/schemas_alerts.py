"""Schémas des alertes et des décisions du gestionnaire."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.schemas_predict import RegleItem, ShapItem

DecisionValue = Literal[
    "VALIDER", "REJETER", "CONFIRMER_FRAUDE", "ESCALADER",
    "fraude_confirmee", "faux_positif", "a_investiguer", "valide", "rejete",
]


class DecisionRequest(BaseModel):
    decision: DecisionValue
    commentaire: str | None = Field(default=None, max_length=1000)
    montant_economise: int | None = Field(default=None, ge=0, le=10**12)  # MGA

    @model_validator(mode="after")
    def montant_seulement_si_fraude(self):
        if self.montant_economise is not None and self.decision not in {"fraude_confirmee", "CONFIRMER_FRAUDE"}:
            raise ValueError("montant_economise n'est accepté que pour confirmer une fraude")
        return self


class DecisionOut(BaseModel):
    decision_id: int
    facture_id: str
    gestionnaire_id: int
    decision: DecisionValue
    commentaire: str | None = None
    montant_economise: int | None = None
    date_decision: datetime


class AlertSummary(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    facture_id: str
    score: float
    version_modele: str
    date: datetime
    montant_total: int | None = None
    prestataire_id: str | None = None
    assure_id: str | None = None
    type_facture: str | None = None
    derniere_decision: DecisionValue | None = None
    date_decision: datetime | None = None
    type: str = "FRAUDE"
    priorite: Literal["FAIBLE", "MOYENNE", "HAUTE"] = "MOYENNE"
    statut: str = "EN_ATTENTE"
    codes: list[str] = Field(default_factory=list)
    etat_notification: Literal["NON_REQUISE", "EN_ATTENTE", "ENVOYEE", "ECHEC"] = "NON_REQUISE"
    tentatives_notification: int = 0
    prestataire_id: str | None = None
    assure_id: str | None = None


class AlertDetailOut(BaseModel):
    """Full manager view of an alert and its explainability data."""

    model_config = ConfigDict(protected_namespaces=())

    prediction: AlertSummary
    shap: list[ShapItem] | dict | None = None
    regles: list[RegleItem] = Field(default_factory=list)
    decisions: list[DecisionOut] = Field(default_factory=list)
    facture: dict = Field(default_factory=dict)
    codes_fraude: list[str] = Field(default_factory=list)


class IdentiteOut(BaseModel):
    assure_id: str
    nom: str | None = None
    prenoms: str | None = None
    telephone: str | None = None
    email: str | None = None
