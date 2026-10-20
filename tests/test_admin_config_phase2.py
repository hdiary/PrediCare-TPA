from fastapi.testclient import TestClient

from api.db import get_db
from api.main import app
from api.security import create_access_token

ROLE_IDS = {
    "professionnel_sante": 1,
    "assure": 2,
    "gestionnaire": 3,
    "administrateur": 4,
}


class Cursor:
    def __init__(self, rows=None, row=None):
        self.rows = rows or []
        self.row = row

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.row


class ConfigConnection:
    def __init__(self):
        self.values = {
            "seuil_alerte": "0.8",
            "condition_etendue": "false",
            "notif_slack": "true",
            "notif_slack_canal": "#alertes-fraude",
            "notif_email": "true",
            "notif_email_destinataire": "gestionnaire@predicare.local; audit@predicare.local",
        }
        self.audit_events = []

    def execute(self, query, params=()):
        normalized = query.strip().upper()
        if "FROM UTILISATEURS" in normalized:
            user_id = params[0]
            role = next(
                role for role, identifier in ROLE_IDS.items() if identifier == user_id
            )
            return Cursor(
                row={
                    "user_id": user_id,
                    "email": f"{role}@predicare.local",
                    "role": role,
                    "assure_id": None,
                    "prestataire_id": None,
                    "is_active": True,
                }
            )
        if "FROM CONFIGURATION WHERE CLE = ANY" in normalized:
            return Cursor(
                rows=[
                    {"cle": key, "valeur": value}
                    for key, value in self.values.items()
                    if key in params[0]
                ]
            )
        if normalized.startswith("INSERT INTO CONFIGURATION"):
            key, value, _ = params
            self.values[key] = value
            return Cursor()
        if "INSERT INTO JOURNAL_AUDIT" in normalized:
            self.audit_events.append(params[0])
            return Cursor()
        raise AssertionError(f"Unexpected query: {query}")


def test_admin_can_read_and_update_configuration():
    connection = ConfigConnection()
    app.dependency_overrides[get_db] = lambda: connection
    token, _ = create_access_token(ROLE_IDS["administrateur"], "administrateur")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = client.get("/api/v1/admin/config", headers=headers)
        assert response.status_code == 200
        assert response.json()["channels"]["slack"]["channel"] == "#alertes-fraude"
        assert client.get("/admin/settings", headers=headers).status_code == 200

        response = client.patch(
            "/api/v1/admin/config",
            headers=headers,
            json={
                "alert_threshold": 0.72,
                "extended_rule_enabled": True,
                "channels": {"slack": {"channel": "#fraude"}},
            },
        )
        assert response.status_code == 200
        assert response.json()["alert_threshold"] == 0.72
        assert response.json()["extended_rule_enabled"] is True
        assert response.json()["channels"]["slack"]["channel"] == "#fraude"
        assert connection.values["seuil_alerte"] == "0.72"
        assert connection.values["condition_etendue"] == "true"
        assert connection.values["notif_slack_canal"] == "#fraude"
        assert connection.audit_events == ["configuration_modifiee"]

        response = client.put(
            "/admin/settings",
            headers=headers,
            json={
                "alert_threshold": 0.68,
                "extended_rule_enabled": False,
                "channels": {
                    "slack": {"enabled": False, "channel": "#fraude"},
                    "email": {
                        "enabled": True,
                        "address": "gestionnaire@example.org; audit@example.org",
                    },
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["alert_threshold"] == 0.68
        assert connection.values["seuil_alerte"] == "0.68"
        assert connection.values["notif_slack"] == "false"
        assert connection.values["notif_email_destinataire"] == (
            "gestionnaire@example.org; audit@example.org"
        )
        assert connection.audit_events == [
            "configuration_modifiee",
            "configuration_modifiee",
        ]

        response = client.patch(
            "/admin/config",
            headers=headers,
            json={"channels": {"slack": {"channel": "not-a-channel"}}},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_admin_email_test_sends_to_configured_recipients(monkeypatch):
    connection = ConfigConnection()
    app.dependency_overrides[get_db] = lambda: connection
    token, _ = create_access_token(ROLE_IDS["administrateur"], "administrateur")
    headers = {"Authorization": f"Bearer {token}"}
    captured = {}
    monkeypatch.setattr("api.routers.admin.smtp_is_configured", lambda: True)
    monkeypatch.setattr(
        "api.routers.admin.send_mail",
        lambda recipients, subject, body: captured.update(
            recipients=recipients, subject=subject, body=body
        ) or True,
    )
    client = TestClient(app)

    try:
        response = client.post("/admin/email/test", headers=headers)
        assert response.status_code == 200
        assert captured["recipients"] == [
            "gestionnaire@predicare.local", "audit@predicare.local"
        ]
        assert connection.audit_events[-1] == "notification_email_test"
    finally:
        app.dependency_overrides.clear()


def test_only_administrator_can_access_configuration():
    connection = ConfigConnection()
    app.dependency_overrides[get_db] = lambda: connection
    client = TestClient(app)

    try:
        for role in ("professionnel_sante", "assure", "gestionnaire"):
            token, _ = create_access_token(ROLE_IDS[role], role)
            headers = {"Authorization": f"Bearer {token}"}
            assert client.get("/admin/config", headers=headers).status_code == 403
            assert client.post("/admin/email/test", headers=headers).status_code == 403
            assert client.patch(
                "/admin/config",
                headers=headers,
                json={"alert_threshold": 0.7},
            ).status_code == 403
            assert client.put(
                "/admin/settings",
                headers=headers,
                json={
                    "alert_threshold": 0.7,
                    "extended_rule_enabled": False,
                    "channels": {
                        "slack": {"enabled": False, "channel": "#fraude"},
                        "email": {"enabled": False, "address": "a@example.org"},
                    },
                },
            ).status_code == 403
    finally:
        app.dependency_overrides.clear()
