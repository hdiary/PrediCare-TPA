"""Schémas des alertes et des décisions du gestionnaire."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DecisionValue = Literal["fraude_confirmee", "faux_positif", "a_investiguer"]


class DecisionRequest(BaseModel):
    decision: DecisionValue
    commentaire: str | None = Field(default=None, max_length=1000)
    montant_economise: int | None = Field(default=None, ge=0, le=10**12)  # MGA

    @model_validator(mode="after")
    def montant_seulement_si_fraude(self):
        if self.montant_economise is not None and self.decision != "fraude_confirmee":
            raise ValueError("montant_economise n'est accepté que pour 'fraude_confirmee'")
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
    nb_regles: int = 0
    derniere_decision: DecisionValue | None = None
    date_decision: datetime | None = None


class IdentiteOut(BaseModel):
    assure_id: str
    nom: str | None = None
    prenoms: str | None = None
    telephone: str | None = None
    email: str | None = None
