from datetime import datetime, timezone

from api.routers import alerts
from api.schemas_alerts import AlertDetailOut


def test_manager_alert_detail_returns_stored_model_inputs(monkeypatch):
    prediction = {"prediction_id": 7, "est_alerte": True}
    summary = {
        "facture_id": "FAC-90000001",
        "score": 0.99995,
        "seuil_utilise": 0.8,
        "version_modele": "hgb-test",
        "date": datetime.now(timezone.utc),
        "montant_total": 12000,
    }
    values = {"age_assure": 42, "delai_facture_reception": 180}
    monkeypatch.setattr(alerts, "_alerte_ou_404", lambda *_args: prediction)
    monkeypatch.setattr(alerts.repo, "get_alert_summary", lambda *_args: summary)
    monkeypatch.setattr(
        alerts.repo, "get_shap", lambda *_args: {"valeurs": {"top": [], "toutes": {}}}
    )
    monkeypatch.setattr(alerts.repo, "get_prediction_variables", lambda *_args: values)
    monkeypatch.setattr(alerts.repo, "list_alertes_regles", lambda *_args: [])
    monkeypatch.setattr(alerts.repo, "get_facture_et_lignes", lambda *_args: ({}, []))
    monkeypatch.setattr(alerts.repo, "list_decisions", lambda *_args: [])

    response = alerts.get_alert("FAC-90000001", conn=object())
    validated = AlertDetailOut.model_validate(response)

    assert validated.variables == values
    assert validated.prediction.seuil_utilise == 0.8
