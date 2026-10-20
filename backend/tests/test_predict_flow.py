"""Tests J3 : /predict, journal d'audit (S8), décisions du gestionnaire, identités."""
import json
from contextlib import nullcontext
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from api.config import get_settings
from api.db import get_db
from api.main import app
from api.security import create_access_token
from api.services.model_registry import ModelBundle, get_registry

USERS = {
    1: dict(user_id=1, email="pro@x", role="professionnel_sante", assure_id=None,
            prestataire_id="PRE-00214", is_active=True),
    3: dict(user_id=3, email="gest@x", role="gestionnaire", assure_id=None,
            prestataire_id=None, is_active=True),
}

VALID = {
    "facture_id": "FAC-00000001",
    "numero_facture": "PRE214/2026/00001",
    "prestataire_id": "PRE-00214",
    "assure_id": "ASS-9CAA1484E0",
    "contrat_id": "CTR-000001",
    "type_facture": "CONSULTATION",
    "date_soin": "2026-10-10",
    "heure_soin": "09:30",
    "devise": "MGA",
    "lignes": [{"code": "CONS-GEN", "type_ligne": "ACTE", "quantite": 1, "prix_unitaire": 25000}],
}


def valid():
    payload = dict(VALID)
    payload["lignes"] = [dict(VALID["lignes"][0])]
    return payload


class Cur:
    def __init__(self, row=None, rows=None):
        self.row, self.rows = row, rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def executemany(self, q, seq):
        pass


class FakeConn:
    def __init__(self, existing_invoice=False):
        self.calls = []
        self.existing_invoice = existing_invoice

    def transaction(self):
        return nullcontext()

    def cursor(self):
        return FakeCursor()

    def commit(self):
        pass

    def audits(self):
        return [
            dict(event_type=p[0], actor=p[1], entity_id=p[3], model_version=p[5],
                 input=p[6].obj if p[6] else None, output=p[7].obj if p[7] else None)
            for q, p in self.calls if q.startswith("INSERT INTO JOURNAL_AUDIT")
        ]

    def executed(self, fragment):
        return [q for q, _ in self.calls if fragment in q]

    def execute(self, query, params=()):
        q = " ".join(query.split()).upper()
        self.calls.append((q, params))
        if "FROM UTILISATEURS WHERE UTILISATEUR_ID" in q:
            return Cur(USERS.get(params[0]))
        if "SELECT 1 AS X FROM FACTURES" in q:
            return Cur({"x": 1} if self.existing_invoice else None)
        if "SELECT ASSURE_ID FROM FACTURES" in q:
            return Cur({"assure_id": "ASS-9CAA1484E0"})
        if "SELECT 1 AS X FROM ASSURES" in q:
            return Cur({"x": 1} if params[0] == "ASS-9CAA1484E0" else None)
        if "SELECT 1 AS X FROM PRESTATAIRES" in q:
            return Cur({"x": 1} if params[0] == "PRE-00214" else None)
        if "FROM GARANTIES" in q:
            return Cur({"x": 1})
        if "FROM REFERENTIEL_ACTES" in q:
            known = {"CONS-GEN", "MED-PARA500"}
            return Cur(rows=[{"code": c, "type_ligne": "ACTE", "libelle": "Libellé"}
                             for c in params[0] if c in known])
        if "FROM CONFIGURATION" in q:
            return Cur({"valeur": "0.8"})
        if "INSERT INTO PREDICTIONS" in q:
            return Cur({"prediction_id": 42})
        if "FROM PREDICTIONS WHERE FACTURE_ID" in q:
            if params[0] == "FAC-00000001":
                return Cur(self._pred(True))
            if params[0] == "FAC-00000002":
                return Cur(self._pred(False))
            return Cur(None)
        if "INSERT INTO DECISIONS_GESTIONNAIRE" in q:
            return Cur({"decision_id": 7, "facture_id": params[1], "gestionnaire_id": params[2],
                        "decision": params[3], "commentaire": params[4],
                        "montant_economise": params[5],
                        "date_decision": datetime(2026, 10, 16, tzinfo=UTC)})
        if "FROM IDENTITES_CHIFFREES" in q:
            payload = {"nom": "RAKOTO", "prenoms": "Jean", "telephone": "034 00 000 00",
                       "email": "j@x.mg", "adresse": "secret", "numero_cin": "123456789012",
                       "date_naissance": "1980-01-01"}
            key = get_settings().identity_encryption_key.encode()
            return Cur({"donnees_chiffrees": Fernet(key).encrypt(json.dumps(payload).encode())})
        return Cur(None)

    @staticmethod
    def _pred(est_alerte):
        return dict(prediction_id=42, facture_id="FAC-00000001", nom_modele="predicare-fraud",
                    version_modele="7", score=0.9, seuil_utilise=0.8, est_alerte=est_alerte,
                    date=datetime(2026, 10, 16, tzinfo=UTC))


class FakeModel:
    def predict_proba(self, X):
        return np.array([[0.1, 0.9]])


class FakeExplainer:
    expected_value = 0.3

    def shap_values(self, X):
        return np.array([[0.5, -0.2, 0.1]])


BUNDLE = ModelBundle("predicare-fraud", "7", FakeModel(), FakeExplainer(),
                     ["f1", "f2", "f3"], datetime.now(UTC))


class FakeRegistry:
    def __init__(self, bundle=BUNDLE):
        self.bundle = bundle
        self.last_error = None

    def ensure_loaded(self):
        return self.bundle

    def get(self):
        return self.bundle


@pytest.fixture
def setup(monkeypatch):
    holder = {"conn": FakeConn(), "registry": FakeRegistry()}
    app.dependency_overrides[get_db] = lambda: holder["conn"]
    app.dependency_overrides[get_registry] = lambda: holder["registry"]
    monkeypatch.setattr(
        "api.routers.predict.build_features",
        lambda payload, conn, expected: pd.DataFrame([[1.0, 2.0, 3.0]], columns=expected),
    )
    yield TestClient(app), holder
    app.dependency_overrides.clear()


def auth(user_id, role):
    return {"Authorization": f"Bearer {create_access_token(user_id, role)[0]}"}


def manager():
    return auth(3, "gestionnaire")


def pro():
    return auth(1, "professionnel_sante")


# ---------- /predict ----------

def test_predict_manager_gets_score_and_shap(setup):
    client, _ = setup
    r = client.post("/predict", json=valid(), headers=manager())
    assert r.status_code == 200
    body = r.json()
    assert body["score"] == pytest.approx(0.9)
    assert body["is_alert"] is True
    assert body["version_modele"] == "7"
    assert body["shap"][0] == {"variable": "f1", "valeur": 1.0, "contribution": 0.5}


def test_predict_provider_does_not_see_score(setup):
    client, _ = setup
    r = client.post("/predict", json=valid(), headers=pro())
    assert r.status_code == 200
    assert "score" not in r.json()
    assert r.json()["prediction_id"] == 42


def test_predict_requires_auth(setup):
    client, _ = setup
    assert client.post("/predict", json=valid()).status_code == 401


def test_invalid_invoice_returns_codes_and_is_audited(setup):
    client, holder = setup
    payload = valid()
    payload["devise"] = "EUR"
    payload["lignes"][0]["prix_unitaire"] = -5
    r = client.post("/predict", json=payload, headers=manager())
    assert r.status_code == 422
    body = r.json()
    assert {"DEVISE_INVALIDE", "MONTANT_NEGATIF"} <= set(body["codes"])
    assert [a["event_type"] for a in holder["conn"].audits()] == ["facture_rejetee"]
    assert not holder["conn"].executed("INSERT INTO FACTURES")


def test_unknown_act_and_unknown_assure_use_database(setup):
    client, _ = setup
    payload = valid()
    payload["lignes"][0]["code"] = "ZZZ-INCONNU"
    payload["assure_id"] = "ASS-0000000000"
    r = client.post("/predict", json=payload, headers=manager())
    assert r.status_code == 422
    assert {"CODE_ACTE_INCONNU", "ASSURE_INCONNU"} <= set(r.json()["codes"])


def test_forbidden_leak_field_rejected(setup):
    client, _ = setup
    payload = valid()
    payload["statut"] = "PAYEE"
    r = client.post("/predict", json=payload, headers=manager())
    assert r.status_code == 422
    assert "CHAMP_INTERDIT" in r.json()["codes"]


def test_duplicate_facture_id_409(setup):
    client, holder = setup
    holder["conn"].existing_invoice = True
    r = client.post("/predict", json=valid(), headers=manager())
    assert r.status_code == 409
    assert "FACTURE_DEJA_ENREGISTREE" in r.json()["codes"]


def test_duplicate_numero_facture_is_not_looked_up(setup):
    client, holder = setup
    assert client.post("/predict", json=valid(), headers=manager()).status_code == 200
    assert not holder["conn"].executed("NUMERO_FACTURE =")


def test_model_unavailable_503(setup):
    client, holder = setup
    holder["registry"] = FakeRegistry(bundle=None)
    assert client.post("/predict", json=valid(), headers=manager()).status_code == 503


# ---------- Test S8 : journal d'audit ----------

def test_s8_prediction_then_decision_are_audited(setup):
    client, holder = setup
    assert client.post("/predict", json=valid(), headers=manager()).status_code == 200
    r = client.post("/alerts/FAC-00000001/decision", headers=manager(),
                    json={"decision": "fraude_confirmee", "commentaire": "doublon",
                          "montant_economise": 21000})
    assert r.status_code == 201

    audits = {a["event_type"]: a for a in holder["conn"].audits()}
    pred, dec = audits["prediction"], audits["decision"]
    assert pred["model_version"] == "7"
    assert pred["input"]["facture_id"] == "FAC-00000001"
    assert pred["output"]["score"] == pytest.approx(0.9)
    assert dec["model_version"] == "7"
    assert dec["input"]["decision"] == "fraude_confirmee"
    assert dec["actor"] == 3


def test_no_automatic_decision(setup):
    client, holder = setup
    client.post("/predict", json=valid(), headers=manager())
    assert not holder["conn"].executed("INSERT INTO DECISIONS_GESTIONNAIRE")


# ---------- décisions ----------

def test_decision_forbidden_for_provider(setup):
    client, _ = setup
    r = client.post("/alerts/FAC-00000001/decision", headers=pro(),
                    json={"decision": "faux_positif"})
    assert r.status_code == 403


def test_decision_unknown_alert_404(setup):
    client, _ = setup
    r = client.post("/alerts/FAC-99999999/decision", headers=manager(),
                    json={"decision": "faux_positif"})
    assert r.status_code == 404


def test_decision_on_non_alert_409(setup):
    client, _ = setup
    r = client.post("/alerts/FAC-00000002/decision", headers=manager(),
                    json={"decision": "faux_positif"})
    assert r.status_code == 409


def test_decision_bad_facture_id_422(setup):
    client, _ = setup
    r = client.post("/alerts/pas-un-id/decision", headers=manager(),
                    json={"decision": "faux_positif"})
    assert r.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"decision": "payer_automatiquement"},
        {"decision": "faux_positif", "montant_economise": 10},
        {"decision": "fraude_confirmee", "montant_economise": -1},
    ],
)
def test_invalid_decision_422(setup, body):
    client, _ = setup
    assert client.post("/alerts/FAC-00000001/decision", headers=manager(),
                       json=body).status_code == 422


# ---------- identités ----------

def test_identity_decrypted_minimized_and_audited(setup):
    client, holder = setup
    r = client.get("/alerts/FAC-00000001/identite", headers=manager())
    assert r.status_code == 200
    body = r.json()
    assert body["nom"] == "RAKOTO"
    assert "numero_cin" not in body and "adresse" not in body
    audit = [a for a in holder["conn"].audits() if a["event_type"] == "acces_identite"][0]
    assert "RAKOTO" not in json.dumps(audit)     # jamais les valeurs dans l'audit


def test_identity_forbidden_for_provider(setup):
    client, _ = setup
    assert client.get("/alerts/FAC-00000001/identite", headers=pro()).status_code == 403
