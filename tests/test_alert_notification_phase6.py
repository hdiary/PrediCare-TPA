from types import SimpleNamespace

from api.services import notify
from test_predict_flow import FakeConn, USERS


PREDICTION = {
    "prediction_id": 9,
    "facture_id": "FAC-00000001",
    "assure_id": "ASS-9CAA1484E0",
    "prestataire_id": "PRE-00214",
    "score": 0.91,
    "seuil": 0.8,
    "version_modele": "7",
    "nom_modele": "predicare-fraud",
    "montant_total": 25000,
}


def configured_settings():
    return SimpleNamespace(
        n8n_webhook_url="http://n8n:5678/webhook/predicare-alert",
        n8n_webhook_secret="test-secret",
        n8n_timeout_s=1.0,
    )


def test_notification_posts_explainability_and_audits_success(monkeypatch):
    conn = FakeConn()
    calls = []
    monkeypatch.setattr(notify, "get_settings", configured_settings)
    monkeypatch.setattr(notify.time, "sleep", lambda _: None)

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=202)

    monkeypatch.setattr(notify.httpx, "post", post)
    success = notify.notification_service(
        conn, USERS[3], PREDICTION,
        [{"variable": "montant_total", "contribution": 0.7}],
        ["SURFACTURATION"], [],
    )

    assert success is True
    assert len(calls) == 1
    assert calls[0][1]["headers"]["X-Webhook-Secret"] == "test-secret"
    assert calls[0][1]["json"]["codes_fraude"] == ["SURFACTURATION"]
    assert calls[0][1]["json"]["shap"][0]["variable"] == "montant_total"
    assert [row["event_type"] for row in conn.audits()] == ["notification_n8n_tentative"]
    assert any("UPDATE ALERTES SET ETAT_NOTIFICATION" in query for query, _ in conn.calls)


def test_notification_retries_three_times_and_keeps_alert_failed(monkeypatch):
    conn = FakeConn()
    calls = []
    monkeypatch.setattr(notify, "get_settings", configured_settings)
    monkeypatch.setattr(notify.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        notify.httpx, "post",
        lambda *args, **kwargs: calls.append(args) or SimpleNamespace(status_code=503),
    )

    success = notify.notification_service(
        conn, USERS[3], PREDICTION, [], ["SURFACTURATION"], [],
    )

    assert success is False
    assert len(calls) == 3
    assert len(conn.audits()) == 3
    state_updates = [(query, params) for query, params in conn.calls if "UPDATE ALERTES SET ETAT_NOTIFICATION" in query]
    assert state_updates[-1][1][:2] == ("ECHEC", 3)
