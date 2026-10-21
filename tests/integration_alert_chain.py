"""End-to-end alert chain runner against an isolated test database.

Required environment: TEST_DATABASE_URL, TEST_PROVIDER_TOKEN, TEST_MANAGER_TOKEN,
TEST_INVOICE_JSON, and API_BASE_URL (defaults to the Compose API service).
Configure the API container's N8N_WEBHOOK_URL to point to a fake receiver for
an isolated notification test. Never point TEST_DATABASE_URL at production.
"""
import json
import os
import sys
import urllib.error
import urllib.request

import psycopg


def require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def request_json(base: str, path: str, token: str, method: str = "GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        base.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        return exc.code, json.loads(payload) if payload else None


def main() -> int:
    database_url = require("TEST_DATABASE_URL")
    provider_token = require("TEST_PROVIDER_TOKEN")
    manager_token = require("TEST_MANAGER_TOKEN")
    invoice = json.loads(require("TEST_INVOICE_JSON"))
    base = os.getenv("API_BASE_URL", "http://api:8000")
    facture_id = invoice["facture_id"]

    # Ensure the supplied database is a test target and the ID is unused.
    with psycopg.connect(database_url) as conn:
        exists = conn.execute(
            "SELECT 1 FROM factures WHERE facture_id = %s", (facture_id,)
        ).fetchone()
        if exists:
            raise RuntimeError(f"Test invoice already exists: {facture_id}; use a fresh ID")

    status, created = request_json(
        base, "/api/v1/factures", provider_token, "POST", invoice
    )
    assert status == 201, f"Invoice submission returned {status}: {created}"
    assert not ({"score", "shap", "codes_fraude", "alerte"} & created.keys()), created

    # The test payload must cross the configured alert threshold and create an alert.
    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            """SELECT f.statut, p.est_alerte, p.score, a.etat_notification,
                      a.tentatives_notification
               FROM factures f JOIN predictions p USING (facture_id)
               JOIN alertes a USING (prediction_id)
               WHERE f.facture_id = %s""",
            (facture_id,),
        ).fetchone()
        assert row and row[1], f"No persisted alert for {facture_id}: {row}"
        assert row[2] is not None, "Alert must have a real model score"
        assert row[3] in {"ENVOYEE", "ECHEC", "EN_ATTENTE", "NON_REQUISE"}, row

    status, listed = request_json(
        base, f"/api/v1/alertes?statut=EN_ATTENTE&type=FRAUDE&limit=200", manager_token
    )
    assert status == 200, f"Alert list returned {status}: {listed}"
    assert any(item["facture_id"] == facture_id for item in listed), "Alert missing from manager list"

    status, detail = request_json(base, f"/api/v1/alertes/{facture_id}", manager_token)
    assert status == 200 and detail["prediction"]["facture_id"] == facture_id, detail
    assert "codes_fraude" in detail and "shap" in detail

    status, decision = request_json(
        base,
        f"/api/v1/alertes/{facture_id}/decision",
        manager_token,
        "PATCH",
        {"decision": "CONFIRMER_FRAUDE", "commentaire": "Scénario d'intégration"},
    )
    assert status == 200, f"Decision returned {status}: {decision}"
    status, duplicate = request_json(
        base,
        f"/api/v1/alertes/{facture_id}/decision",
        manager_token,
        "PATCH",
        {"decision": "REJETER", "commentaire": "Double décision"},
    )
    assert status == 409, f"Duplicate decision must return 409, got {status}: {duplicate}"

    with psycopg.connect(database_url) as conn:
        invoice_status = conn.execute(
            "SELECT statut FROM factures WHERE facture_id = %s", (facture_id,)
        ).fetchone()
        decision_row = conn.execute(
            """SELECT decision FROM decisions_gestionnaire
               WHERE facture_id = %s ORDER BY date_decision DESC LIMIT 1""",
            (facture_id,),
        ).fetchone()
        audit_row = conn.execute(
            """SELECT 1 FROM journal_audit
               WHERE entite_id = %s AND type_evenement = 'decision' LIMIT 1""",
            (facture_id,),
        ).fetchone()
        notification_rows = conn.execute(
            """SELECT count(*) FROM journal_audit
               WHERE entite_id = %s AND type_evenement = 'notification_n8n_tentative'""",
            (facture_id,),
        ).fetchone()[0]
        assert invoice_status and invoice_status[0] == "REJETEE", invoice_status
        assert decision_row and decision_row[0] == "fraude_confirmee", decision_row
        assert audit_row, "Decision missing from journal_audit"
        assert notification_rows >= 1, "Webhook attempt missing from journal_audit"

    print(f"PASS alert-chain facture={facture_id} webhook={row[3]} attempts={row[4]} audit_attempts={notification_rows} decision=fraude_confirmee")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # Report integration failures as concise runner output.
        print(f"FAIL alert-chain: {exc}", file=sys.stderr)
        raise
