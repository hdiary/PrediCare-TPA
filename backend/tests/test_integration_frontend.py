"""Intégration : les routes utilisées par le frontend, contre un vrai PostgreSQL."""

import os
import pathlib
from types import SimpleNamespace

import numpy as np
import pandas as pd
import psycopg
import pytest
from fastapi.testclient import TestClient

BASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not BASE_URL, reason="TEST_DATABASE_URL non défini")

MDP = "Mot-de-passe-test-1"
FACTURE = {
    "facture_id": "FAC-90000001",
    "numero_facture": "PRE214/2026/00001",
    "prestataire_id": "PRE-00214",
    "assure_id": "ASS-9CAA1484E0",
    "contrat_id": "CTR-000001",
    "type_facture": "CONSULTATION",
    "date_soin": "2026-10-10",
    "heure_soin": "09:30",
    "devise": "MGA",
    "lignes": [
        {"code": "CONS-GEN", "quantite": 2, "prix_unitaire": 25000},
        {"code": "MED-1", "quantite": 1, "prix_unitaire": 4000},
    ],
}


class FauxModele:
    """Remplace MLflow : score fixe, SHAP fixe."""

    classes_ = [0, 1]

    def __init__(self, score):
        self.score = score

    def predict_proba(self, X):
        return np.array([[1 - self.score, self.score]])


class FauxExplainer:
    expected_value = 0.1

    def shap_values(self, X):
        return np.array([[0.41, -0.05]])


class FauxRegistre:
    def __init__(self):
        self.bundle = SimpleNamespace(
            name="predicare-fraud",
            version="7",
            model=FauxModele(0.91),
            explainer=FauxExplainer(),
            feature_names=["ecart_prix", "nb"],
        )
        self.last_error = None

    def ensure_loaded(self):
        return self.bundle

    def get(self):
        return self.bundle


@pytest.fixture(scope="module")
def client():
    admin_url = BASE_URL
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute("DROP DATABASE IF EXISTS predicare_it")
        c.execute("CREATE DATABASE predicare_it")
    db_url = os.environ["DATABASE_URL"]
    from api.security import hash_password

    with psycopg.connect(db_url, autocommit=True) as c:
        c.execute((pathlib.Path(__file__).parent / "schema_test.sql").read_text())
        for username, role, ass, pre in [
            ("pro@t.mg", "professionnel_sante", None, "PRE-00214"),
            ("pro2@t.mg", "professionnel_sante", None, "PRE-00999"),
            ("assure@t.mg", "assure", "ASS-9CAA1484E0", None),
            ("assure2@t.mg", "assure", "ASS-1111111111", None),
            ("gest@t.mg", "gestionnaire", None, None),
            ("admin@t.mg", "administrateur", None, None),
        ]:
            user = c.execute(
                "INSERT INTO utilisateurs "
                "(nom_utilisateur, hash_mot_de_passe, assure_id, prestataire_id) "
                "VALUES (%s,%s,%s,%s) RETURNING utilisateur_id",
                (username, hash_password(MDP), ass, pre),
            ).fetchone()
            c.execute(
                "INSERT INTO utilisateurs_roles (utilisateur_id, role_id) "
                "SELECT %s, role_id FROM roles WHERE nom_role = %s",
                (user[0], role),
            )
    import api.routers.predict as predict_mod
    from api.main import app
    from api.services.model_registry import get_registry

    predict_mod.build_features = lambda clean, conn, names: pd.DataFrame([[3.2, 6]], columns=names)
    app.dependency_overrides[get_registry] = lambda: FauxRegistre()
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def _token(client, email, mdp=MDP):
    r = client.post("/auth/login", json={"email": email, "password": mdp})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def h(client):
    return {
        k: _token(client, f"{k}@t.mg")
        for k in ("pro", "pro2", "assure", "assure2", "gest", "admin")
    }


def test_login_et_me(client, h):
    r = client.get("/auth/me", headers=h["pro"])
    assert r.status_code == 200
    assert r.json()["role"] == "professionnel_sante" and r.json()["prestataire_id"] == "PRE-00214"
    bad = client.post("/auth/login", json={"email": "pro@t.mg", "password": "faux"})
    assert bad.status_code == 401


def test_depot_facture_pro_accuse_sans_score(client, h):
    r = client.post("/predict", json=FACTURE, headers=h["pro"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepte"] is True and body["facture_id"] == "FAC-90000001"
    assert "score" not in body and "shap" not in body  # le prestataire ne voit pas le score


def test_depot_facture_doublon_409(client, h):
    r = client.post("/predict", json=FACTURE, headers=h["pro"])
    assert r.status_code == 409 and r.json()["codes"] == ["FACTURE_DEJA_ENREGISTREE"]


def test_depot_facture_invalide_422_codes(client, h):
    bad = {
        **FACTURE,
        "facture_id": "FAC-90000002",
        "devise": "USD",
        "lignes": [{"code": "INCONNU", "quantite": 1, "prix_unitaire": 10}],
    }
    r = client.post("/predict", json=bad, headers=h["pro"])
    assert r.status_code == 422
    assert set(r.json()["codes"]) == {"DEVISE_INVALIDE", "CODE_ACTE_INCONNU"}
    assert all({"code", "champ", "message"} <= set(e) for e in r.json()["erreurs"])


def test_depot_pour_autre_prestataire_403(client, h):
    r = client.post("/predict", json={**FACTURE, "facture_id": "FAC-90000003"}, headers=h["pro2"])
    assert r.status_code == 403 and r.json()["codes"] == ["PRESTATAIRE_NON_AUTORISE"]


def test_alertes_listes_et_detail(client, h):
    assert client.get("/alerts", headers=h["pro"]).status_code == 403
    r = client.get("/alerts?statut=en_attente", headers=h["gest"])
    assert r.status_code == 200 and len(r.json()) == 1
    a = r.json()[0]
    assert a["facture_id"] == "FAC-90000001" and a["score"] == pytest.approx(0.91)
    assert a["prestataire_id"] == "PRE-00214" and a["assure_id"] == "ASS-9CAA1484E0"
    assert a["type_facture"] == "CONSULTATION" and a["montant_total"] == 54000
    d = client.get("/alerts/FAC-90000001", headers=h["gest"]).json()
    assert d["facture"]["numero_facture"] == "PRE214/2026/00001"
    assert [ln["code"] for ln in d["lignes"]] == ["CONS-GEN", "MED-1"]
    assert (
        d["lignes"][0]["libelle"] == "Consultation générale" and d["lignes"][0]["montant"] == 50000
    )
    assert d["shap"]["top"][0]["variable"] == "ecart_prix" and d["decisions"] == []
    assert d["historique_prestataire"] == []  # aucune décision antérieure


def test_factures_perimetre_par_role(client, h):
    def ids(hdr):
        items = client.get("/invoices", headers=hdr).json()["items"]
        return [f["facture_id"] for f in items]

    assert ids(h["pro"]) == ["FAC-90000001"]
    assert ids(h["pro2"]) == []  # autre établissement : rien
    assert ids(h["assure"]) == ["FAC-90000001"]
    assert ids(h["assure2"]) == []
    assert ids(h["gest"]) == ["FAC-90000001"]
    assert client.get("/invoices", headers=h["admin"]).status_code == 403
    f = client.get("/invoices", headers=h["assure"]).json()["items"][0]
    assert f["statut"] == "EN_COURS" and len(f["lignes"]) == 2 and f["montant_total"] == 54000
    assert client.get("/invoices?statut=PAYEE", headers=h["gest"]).json()["total"] == 0


def test_decision_puis_listes(client, h):
    r = client.post(
        "/alerts/FAC-90000001/decision",
        headers=h["gest"],
        json={"decision": "fraude_confirmee", "commentaire": "ok", "montant_economise": 50000},
    )
    assert r.status_code == 201
    assert client.get("/alerts?statut=en_attente", headers=h["gest"]).json() == []
    t = client.get("/alerts?statut=toutes", headers=h["gest"]).json()
    assert t[0]["derniere_decision"] == "fraude_confirmee"
    d = client.get("/alerts/FAC-90000001", headers=h["gest"]).json()
    assert (
        d["decisions"][0]["gestionnaire_id"] and d["decisions"][0]["decision"] == "fraude_confirmee"
    )
    # une 2e alerte du même prestataire voit cette décision dans son historique :
    r2 = client.post("/predict", json={**FACTURE, "facture_id": "FAC-90000009"}, headers=h["gest"])
    assert r2.json()["is_alert"] is True
    h2 = client.get("/alerts/FAC-90000009", headers=h["gest"]).json()["historique_prestataire"]
    assert [x["facture_id"] for x in h2] == ["FAC-90000001"] and h2[0][
        "decision"
    ] == "fraude_confirmee"


def test_parametres_admin_et_seuil_en_direct(client, h):
    assert client.get("/admin/settings", headers=h["gest"]).status_code == 403
    s = client.get("/admin/settings", headers=h["admin"]).json()
    assert s["alert_threshold"] == pytest.approx(0.8) and s["slack_enabled"] is False
    maj = {
        "alert_threshold": 0.95,
        "slack_enabled": True,
        "slack_channel": "#predicare-alertes",
        "email_enabled": True,
        "email_recipients": "a@b.mg, c@d.mg",
    }
    assert client.put("/admin/settings", json=maj, headers=h["admin"]).status_code == 200
    assert (
        client.get("/admin/settings", headers=h["admin"]).json()["email_recipients"]
        == "a@b.mg, c@d.mg"
    )
    # le nouveau seuil s'applique à la prédiction suivante, sans redémarrage :
    r = client.post("/predict", json={**FACTURE, "facture_id": "FAC-90000004"}, headers=h["gest"])
    assert r.status_code == 200 and r.json()["seuil"] == pytest.approx(0.95)
    assert r.json()["is_alert"] is False  # 0,91 < 0,95
    for mauvais in (
        {**maj, "alert_threshold": 1.5},
        {**maj, "slack_channel": "pas un canal!"},
        {**maj, "email_recipients": "pas-un-mail"},
    ):
        assert client.put("/admin/settings", json=mauvais, headers=h["admin"]).status_code == 422


def test_journal_audit_et_utilisateurs(client, h):
    assert client.get("/admin/audit-log", headers=h["gest"]).status_code == 403
    log = client.get("/admin/audit-log", headers=h["admin"]).json()
    types = {e["event_type"] for e in log}
    assert {"prediction", "decision", "config_modifiee", "facture_rejetee"} <= types
    assert all(e["actor"] == "SYSTEME" or "-" in e["actor"] for e in log)
    only = client.get("/admin/audit-log?event_type=decision", headers=h["admin"]).json()
    assert only and {e["event_type"] for e in only} == {"decision"}
    users = client.get("/admin/users", headers=h["admin"]).json()
    assert len(users) == 6 and all(
        "mot_de_passe_hash" not in u and "hash" not in str(u) for u in users
    )
    assert client.get("/admin/users", headers=h["pro"]).status_code == 403
