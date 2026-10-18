"""Réponse de /predict (contrat 11.1) et exemple de requête pour la documentation."""
from pydantic import BaseModel, ConfigDict


class ShapItem(BaseModel):
    variable: str
    valeur: float | str | None = None
    contribution: float


class RegleItem(BaseModel):
    regle_code: str
    severite: str
    message: str
    details: dict | None = None


class PredictResponse(BaseModel):
    """Gestionnaire : réponse complète. Professionnel de santé : accusé de réception seul."""

    model_config = ConfigDict(protected_namespaces=())

    accepte: bool = True
    facture_id: str
    prediction_id: int
    score: float | None = None
    seuil: float | None = None
    is_alert: bool | None = None
    version_modele: str | None = None
    shap: list[ShapItem] | None = None
    latence_ms: int | None = None
    regles: list[RegleItem] | None = None   # alertes de règles de prescription (gestionnaire)


PREDICT_REQUEST_EXAMPLE = {
    "facture_id": "FAC-90000001",
    "numero_facture": "PRE214/2026/00001",
    "prestataire_id": "PRE-00214",
    "assure_id": "ASS-9CAA1484E0",
    "contrat_id": "CTR-000001",
    "ordonnance_id": "ORD-0000001",
    "type_facture": "CONSULTATION",
    "date_soin": "2026-10-10",
    "heure_soin": "09:30",
    "devise": "MGA",
    "lignes": [
        {"code": "CONS-GEN", "type_ligne": "ACTE", "quantite": 1, "prix_unitaire": 25000}
    ],
}

PREDICT_OPENAPI_EXTRA = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"type": "object", "title": "Facture"},
                "example": PREDICT_REQUEST_EXAMPLE,
            }
        },
    }
}
