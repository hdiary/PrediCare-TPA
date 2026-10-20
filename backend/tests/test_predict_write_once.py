from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

from api.routers import predict


def test_successful_prediction_persists_invoice_once(monkeypatch):
    clean = {
        "facture_id": "FAC-90000001",
        "prestataire_id": "PRE-00214",
        "assure_id": "ASS-1234567890",
        "montant_total": 1000,
    }
    monkeypatch.setattr(predict, "validate_invoice", lambda _payload, _conn: ([], clean))
    monkeypatch.setattr(predict, "build_context", lambda _conn, _clean: {})
    monkeypatch.setattr(predict, "calculate_reimbursement", lambda _clean, _context: None)
    monkeypatch.setattr(predict, "evaluate_fraud_rules", lambda _clean, _context: [])
    monkeypatch.setattr(predict, "build_features", lambda *_args: pd.DataFrame({"feature": [1.0]}))
    monkeypatch.setattr(
        predict,
        "predict_with_explanation",
        lambda *_args: {
            "score": 0.1,
            "variables": {"feature": 1.0},
            "shap_complet": {},
            "shap": [],
        },
    )
    monkeypatch.setattr(predict, "evaluate_rules", lambda _conn, _clean: [])

    repo = SimpleNamespace(
        facture_existe=lambda _conn, _facture_id: False,
        get_seuil_alerte=lambda _conn, _default: 0.7,
        insert_facture=MagicMock(),
        insert_calculation=MagicMock(),
        insert_prediction=MagicMock(return_value=7),
        insert_shap=MagicMock(),
        insert_alertes_regles=MagicMock(),
        insert_alert=MagicMock(),
    )
    monkeypatch.setattr(predict, "repo", repo)
    monkeypatch.setattr(predict, "write_audit", MagicMock())

    conn = MagicMock()
    registry = SimpleNamespace(
        ensure_loaded=lambda: SimpleNamespace(name="test", version="v1", feature_names=["feature"])
    )

    response = predict.predict(
        payload=clean,
        user={"user_id": 1, "role": "gestionnaire"},
        conn=conn,
        registry=registry,
    )

    assert response.facture_id == clean["facture_id"]
    repo.insert_facture.assert_called_once()
    repo.insert_prediction.assert_called_once()
    repo.insert_shap.assert_called_once()
