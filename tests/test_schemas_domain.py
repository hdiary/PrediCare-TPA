"""Contract tests for the phase 3 business schemas."""

from datetime import date

import pytest
from pydantic import ValidationError

from api.schemas_alerts import AlertDetailOut, AlertSummary, DecisionRequest
from api.schemas_domain import FacturePrestataireOut, InvoiceCreate


def invoice_payload() -> dict:
    return {
        "facture_id": "FAC-12345678",
        "numero_facture": "PRE-2026-001",
        "assure_id": "ASS-0123456789",
        "contrat_id": "CTR-123456",
        "type_facture": "CONSULTATION",
        "date_soin": "2026-10-01",
        "heure_soin": "09:00:00",
        "date_facture": "2026-10-01",
        "lignes": [
            {
                "num_ligne": 1,
                "code": "CONS-GEN",
                "type_ligne": "ACTE",
                "libelle": "Consultation générale",
                "quantite": 2,
                "prix_unitaire": 100,
                "montant": 200,
            }
        ],
        "montant_total": 200,
    }


def test_invoice_create_accepts_valid_payload_and_assure_id():
    invoice = InvoiceCreate.model_validate(invoice_payload())

    assert invoice.assure_id == "ASS-0123456789"
    assert invoice.montant_total == 200


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("assure_id", "ASS-invalid"),
        ("devise", "EUR"),
        ("type_facture", "UNKNOWN"),
    ],
)
def test_invoice_create_rejects_invalid_enum_or_identifier(field, value):
    payload = invoice_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        InvoiceCreate.model_validate(payload)


def test_invoice_create_rejects_inconsistent_line_amount():
    payload = invoice_payload()
    payload["lignes"][0]["montant"] = 201
    payload["montant_total"] = 201

    with pytest.raises(ValidationError, match="montant de la ligne"):
        InvoiceCreate.model_validate(payload)


def test_invoice_create_rejects_duplicate_line_numbers():
    payload = invoice_payload()
    payload["lignes"].append({**payload["lignes"][0], "code": "B", "num_ligne": 1})
    payload["montant_total"] = 400

    with pytest.raises(ValidationError, match="numéros de ligne"):
        InvoiceCreate.model_validate(payload)


def test_invoice_create_rejects_provider_id_in_request():
    payload = invoice_payload()
    payload["prestataire_id"] = "PRE-12345"

    with pytest.raises(ValidationError, match="prestataire_id"):
        InvoiceCreate.model_validate(payload)


def test_provider_output_contains_no_sensitive_prediction_fields():
    output = FacturePrestataireOut(
        facture_id="FAC-12345678",
        numero_facture="PRE-2026-001",
        type_facture="CONSULTATION",
        date_soin=date(2026, 10, 1),
        montant_total=200,
        devise="MGA",
        statut="EN_ATTENTE_GESTIONNAIRE",
    )

    assert "score" not in output.model_dump()
    assert "shap" not in output.model_dump()
    serialized = output.model_dump()
    for field in ("score", "shap", "codes_fraude", "alerte", "type_fraude"):
        assert field not in serialized


def test_manager_alert_schemas_accept_decision_and_detail():
    decision = DecisionRequest(decision="fraude_confirmee", montant_economise=100)
    alert = AlertSummary(
        facture_id="FAC-12345678",
        score=0.95,
        version_modele="2",
        date="2026-10-01T09:00:00Z",
    )
    detail = AlertDetailOut(prediction=alert, decisions=[])

    assert decision.decision == "fraude_confirmee"
    assert detail.prediction.facture_id == "FAC-12345678"
