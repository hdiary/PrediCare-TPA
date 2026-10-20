from datetime import UTC, datetime

from fastapi.testclient import TestClient

from api import repositories as repo
from api.db import get_db
from api.deps import get_current_user
from api.main import app


class QueryResult:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class AlertDetailConn:
    def __init__(self, facture, lignes, historique):
        self.facture = facture
        self.lignes = lignes
        self.historique = historique

    def execute(self, query, params=()):
        statement = " ".join(query.split()).upper()
        if "FROM FACTURES WHERE FACTURE_ID = %S" in statement:
            return QueryResult(row=self.facture)
        if "FROM LIGNES_FACTURE WHERE FACTURE_ID = ANY(%S)" in statement:
            return QueryResult(rows=self.lignes)
        if "FROM DECISIONS_GESTIONNAIRE D" in statement:
            return QueryResult(rows=self.historique)
        raise AssertionError(f"Unexpected query: {statement}")


def test_alert_detail_returns_frontend_fields_and_cors(monkeypatch):
    now = datetime(2026, 10, 16, tzinfo=UTC)
    facture_id = "FAC-98335662"
    facture = {
        "facture_id": facture_id,
        "numero_facture": "PRE214/2026/00001",
        "prestataire_id": "PRE-00214",
        "assure_id": "ASS-9CAA1484E0",
        "montant_total": 54000,
    }
    lignes = [{
        "num_ligne": 1,
        "code": "CONS-GEN",
        "libelle": "Consultation générale",
        "quantite": 1,
        "prix_unitaire": 54000,
        "montant": 54000,
    }]
    historique = [{
        "facture_id": "FAC-90000001",
        "score": 0.91,
        "decision": "fraude_confirmee",
        "date_decision": now,
        "gestionnaire_id": 3,
    }]
    summary = {
        "facture_id": facture_id,
        "score": 0.91,
        "version_modele": "7",
        "date": now,
        "montant_total": 54000,
        "nb_regles": 1,
        "prestataire_id": "PRE-00214",
        "assure_id": "ASS-9CAA1484E0",
    }

    conn = AlertDetailConn(
        facture,
        [{"facture_id": facture_id, **lignes[0]}],
        historique,
    )
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: conn)
    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: {"user_id": 3, "role": "gestionnaire"},
    )
    monkeypatch.setattr(
        repo, "get_prediction",
        lambda conn, invoice_id: {
            "prediction_id": 42,
            "facture_id": invoice_id,
            "est_alerte": True,
        },
    )
    monkeypatch.setattr(repo, "get_alert_summary", lambda conn, invoice_id: summary)
    monkeypatch.setattr(repo, "get_shap", lambda conn, prediction_id: None)
    monkeypatch.setattr(repo, "list_alertes_regles", lambda conn, prediction_id: [])
    monkeypatch.setattr(repo, "list_decisions", lambda conn, prediction_id: [])

    response = TestClient(app).get(
        f"/alerts/{facture_id}",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"]
    body = response.json()
    assert body["facture"]["prestataire_id"] == "PRE-00214"
    assert body["lignes"] == lignes
    assert body["historique_prestataire"][0]["facture_id"] == "FAC-90000001"
