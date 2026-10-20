from types import SimpleNamespace

from api.services import mailer


class FakeSMTP:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.started_tls = False
        self.sent = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self, **_):
        self.started_tls = True

    def login(self, username, password):
        self.credentials = (username, password)

    def send_message(self, message, to_addrs):
        self.sent = (message, to_addrs)


def test_send_mail_uses_starttls_and_hides_multiple_recipients(monkeypatch):
    smtp = FakeSMTP()
    monkeypatch.setattr(mailer, "get_settings", lambda: SimpleNamespace(
        smtp_host="smtp.example.org", smtp_port=587,
        smtp_from="alerts@example.org", smtp_starttls=True,
        smtp_user="sender", smtp_password="secret",
    ))
    monkeypatch.setattr(mailer.smtplib, "SMTP", lambda *args, **kwargs: smtp)

    sent = mailer.send_mail(
        ["manager@example.org", "audit@example.org"], "Subject", "Body"
    )

    assert sent is True
    assert smtp.started_tls is True
    assert smtp.credentials == ("sender", "secret")
    assert smtp.sent[1] == ["manager@example.org", "audit@example.org"]
    assert smtp.sent[0]["To"] == "undisclosed-recipients:;"


def test_alert_email_uses_configured_recipients_without_insured_identity(monkeypatch):
    captured = {}
    monkeypatch.setattr(mailer.repo, "get_config_values", lambda _conn, _keys: {
        "notif_email": {"valeur": "true"},
        "notif_email_destinataire": {
            "valeur": "manager@example.org; audit@example.org"
        },
    })
    monkeypatch.setattr(
        mailer, "send_mail",
        lambda recipients, subject, body: captured.update(
            recipients=recipients, subject=subject, body=body
        ) or True,
    )

    sent = mailer.send_alert_email(object(), {
        "facture_id": "FAC-00000001",
        "score": 0.91,
        "seuil": 0.8,
        "montant_total": 25000,
        "codes_fraude": ["SURFACTURATION"],
    })

    assert sent is True
    assert captured["recipients"] == ["manager@example.org", "audit@example.org"]
    assert "FAC-00000001" in captured["subject"]
    assert "SURFACTURATION" in captured["body"]
    assert "Aucune identité" in captured["body"]


def test_alert_email_skips_when_channel_is_disabled(monkeypatch):
    monkeypatch.setattr(mailer.repo, "get_config_values", lambda _conn, _keys: {
        "notif_email": {"valeur": "false"},
        "notif_email_destinataire": {"valeur": "manager@example.org"},
    })
    monkeypatch.setattr(
        mailer, "send_mail", lambda *_args: (_ for _ in ()).throw(AssertionError())
    )

    assert mailer.send_alert_email(object(), {"facture_id": "FAC-1"}) is False