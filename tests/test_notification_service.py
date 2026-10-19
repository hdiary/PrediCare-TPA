from types import SimpleNamespace

from api.services.notification_service import notify_alert


ALERT = {
    "alert_id": 4,
    "facture_id": "FAC-00000001",
    "score": 0.91,
    "shap": [{"variable": "montant_total", "contribution": 0.7}] * 6,
    "codes_fraude": ["SURFACTURATION"],
    "montant_reclame": 25000,
    "montant_calcule": 10000,
}


def settings():
    return SimpleNamespace(
        n8n_webhook_url="http://n8n.test/webhook",
        n8n_webhook_secret="test-secret",
        n8n_timeout_s=1,
        n8n_retry_delay_s=0,
    )


def test_notify_alert_succeeds_on_first_attempt():
    attempts = []
    audits = []
    client = SimpleNamespace(
        post=lambda *args, **kwargs: attempts.append(kwargs)
        or SimpleNamespace(status_code=202)
    )

    result = notify_alert(ALERT, client=client, settings=settings(), audit=audits.append)

    assert result == "SENT"
    assert len(attempts) == 1
    assert audits == [{"attempt": 1, "success": True, "result": 202}]
    assert len(attempts[0]["json"]["shap"]) == 5
    assert all("test-secret" not in repr(audit) for audit in audits)


def test_notify_alert_succeeds_on_third_attempt():
    calls = 0
    audits = []

    def post(*args, **kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(status_code=202 if calls == 3 else 503)

    result = notify_alert(
        ALERT, client=SimpleNamespace(post=post), settings=settings(), audit=audits.append
    )

    assert result == "SENT"
    assert calls == 3
    assert [audit["attempt"] for audit in audits] == [1, 2, 3]


def test_notify_alert_returns_failed_after_three_attempts_without_raising():
    audits = []
    client = SimpleNamespace(post=lambda *args, **kwargs: SimpleNamespace(status_code=503))

    result = notify_alert(ALERT, client=client, settings=settings(), audit=audits.append)

    assert result == "FAILED"
    assert len(audits) == 3
    assert all("test-secret" not in repr(audit) for audit in audits)
