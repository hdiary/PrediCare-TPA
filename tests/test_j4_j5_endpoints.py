"""Tests J4-J5 : /kpis, règles de prescription, administration, métriques, dérive, support front.

Réutilise les faux (FakeConn, USERS, BUNDLE) de test_predict_flow.py.
"""
from datetime import UTC, date, datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.db import get_db
from api.main import app
from api.security import create_access_token
from api.services.model_registry import ModelBundle, ModelUnavailableError, get_registry
from test_predict_flow import BUNDLE, USERS, Cur, FakeConn, FakeCursor, valid

USERS[2] = dict(user_id=2, email="assure@x", role="assure", assure_id="ASS-9CAA1484E0",
                prestataire_id=None, is_active=True)
USERS[4] = dict(user_id=4, email="admin@x", role="administrateur", assure_id=None,
                prestataire_id=None, is_active=True)
NOW = datetime(2026, 10, 16, tzinfo=UTC)


class RecCursor(FakeCursor):
    def __init__(self, conn):
        self.conn = conn

    def executemany(self, q, seq):
        self.conn.calls.append((" ".join(q.split()).upper(), list(seq)))


class AdminConn(FakeConn):
    """Base factice : configuration modifiable + réponses aux requêtes de J4-J5."""

    def __init__(self):
        super().__init__()
        self.config = {"seuil_alerte": "0.8"}
        self.model_history = [{"prev": "6", "v": "7"}]
        self.n_drift = 50

    def cursor(self):
        return RecCursor(self)

    def execute(self, query, params=()):
        q = " ".join(query.split()).upper()
        self.calls.append((q, params))
        r = self._answer(q, params)
        if r is not None:
            return r
        self.calls.pop()                       # laissé à FakeConn, qui enregistre lui-même
        return super().execute(query, params)

    def _answer(self, q, params):
        if q.startswith("INSERT INTO CONFIGURATION"):
            self.config[params[0]] = params[1]
            return Cur(None)
        if "FROM CONFIGURATION" in q:
            if "REGLE_QUANTITE" in q:
                return Cur({"valeur": "10"})
            cle = params[0] if params else "seuil_alerte"
            return Cur({"cle": cle, "valeur": self.config[cle], "mis_a_jour_le": NOW,
                        "mis_a_jour_par": "admin@x"})
        if "NB_REGLES" in q:
            return Cur(rows=[dict(facture_id="FAC-00000001", score=0.9, version_modele="7",
                                  date=NOW, montant_total=25000, nb_regles=2,
                                  derniere_decision=None, date_decision=None)])
        if q.startswith("SELECT COUNT(*) AS N FROM PREDICTIONS P"):
            return Cur({"n": 3})
        if "COUNT(*) AS FACTURES_SCOREES" in q:
            return Cur(dict(factures_scorees=10, alertes_total=4, alertes_en_attente=1,
                            alertes_traitees=3, fraudes_confirmees=2, faux_positifs=1,
                            a_investiguer=0, montant_en_attente=500000,
                            montant_fraude_confirmee=900000, score_moyen=0.31))
        if "AS TOTAL" in q and "MONTANT_ECONOMISE" in q:
            return Cur({"total": 150000})
        if "P.DATE::DATE AS JOUR" in q:
            return Cur(rows=[dict(jour=date(2026, 10, 15), factures=4, alertes=1)])
        if "FROM ALERTES_PRESCRIPTION" in q and "GROUP BY" in q:
            return Cur(rows=[dict(regle_code="ORDONNANCE_REUTILISEE", n=2)])
        if "FROM ALERTES_PRESCRIPTION WHERE PREDICTION_ID" in q:
            return Cur(rows=[dict(alerte_regle_id=1, regle_code="QUANTITE_ANORMALE",
                                  severite="moyenne", message="m", details={"seuil": 10},
                                  cree_le=NOW)])
        if "FROM REFERENTIEL_ACTES" in q:
            known = {"CONS-GEN": "ACTE", "MED-PARA500": "MEDICAMENT"}
            return Cur(rows=[dict(code=c, type_ligne=known[c], libelle="L")
                             for c in params[0] if c in known])
        if "PERCENTILE_CONT" in q:
            return Cur(dict(volume=10, alertes=2, p50=12.0, p95=40.0, max_latence=55))
        if "FROM JOURNAL_AUDIT WHERE HORODATAGE >=" in q:
            return Cur(rows=[dict(type_evenement="facture_rejetee", n=3)])
        if q.startswith("SELECT AUDIT_ID"):
            return Cur(rows=[dict(audit_id=1, horodatage=NOW, type_evenement="prediction",
                                  utilisateur_id=3, type_entite="facture", entite_id="FAC-1",
                                  nom_modele="m", version_modele="7", entree={"a": 1},
                                  sortie={"b": 2})])
        if "ENTREE->>'PREVIOUS_VERSION'" in q:
            return Cur(rows=self.model_history)
        if "VALEURS->'TOUTES'" in q:
            return Cur(rows=[{"toutes": {"x": 0.9, "y": 0.1}}] * 20)
        if "FROM PREDICTIONS WHERE VARIABLES IS NOT NULL" in q:
            if "MAKE_INTERVAL" in q:
                return Cur(rows=[{"variables": {"x": float(i + 100), "y": 1}}
                                 for i in range(self.n_drift)])
            return Cur(rows=[{"variables": {"x": float(i), "y": 1}} for i in range(self.n_drift)])
        return None


class AdminRegistry:
    def __init__(self):
        self.bundle, self.last_error, self.fail = BUNDLE, None, False

    def get(self):
        return self.bundle

    def ensure_loaded(self):
        return self.bundle

    def load_active(self, force=False):
        return self.bundle

    def list_versions(self):
        if self.fail:
            raise ModelUnavailableError("mlflow indisponible")
        return [dict(version="7", aliases=["champion"], statut="READY", run_id="r7",
                     cree_le=None, charge=True),
                dict(version="6", aliases=[], statut="READY", run_id="r6",
                     cree_le=None, charge=False)]

    def activate_version(self, version):
        if self.fail:
            raise ModelUnavailableError("échec du chargement")
        self.bundle = ModelBundle("predicare-fraud", str(version), BUNDLE.model, BUNDLE.explainer,
                                  BUNDLE.feature_names, datetime.now(UTC))
        return self.bundle


@pytest.fixture
def env(monkeypatch):
    holder = {"conn": AdminConn(), "registry": AdminRegistry()}
    app.dependency_overrides[get_db] = lambda: holder["conn"]
    app.dependency_overrides[get_registry] = lambda: holder["registry"]
    monkeypatch.setattr(
        "api.routers.predict.build_features",
        lambda payload, conn, expected: pd.DataFrame([[1.0, 2.0, 3.0]], columns=expected),
    )
    yield TestClient(app), holder
    app.dependency_overrides.clear()


def as_user(uid):
    role = USERS[uid]["role"]
    return {"Authorization": f"Bearer {create_access_token(uid, role)[0]}"}


PRO, ASSURE, MANAGER, ADMIN = as_user(1), as_user(2), as_user(3), as_user(4)

# ---------------- S1 : les nouveaux endpoints respectent la matrice des rôles ----------------

NEW_ENDPOINTS = [
    ("GET", "/kpis", None, {"gestionnaire", "administrateur"}),
    ("GET", "/admin/threshold", None, {"administrateur"}),
    ("PUT", "/admin/threshold", {"seuil": 0.7}, {"administrateur"}),
    ("GET", "/admin/model/versions", None, {"administrateur"}),
    ("POST", "/admin/model/activate", {"version": "6"}, {"administrateur"}),
    ("POST", "/admin/model/rollback", None, {"administrateur"}),
    ("GET", "/admin/audit", None, {"administrateur"}),
    ("GET", "/admin/metrics", None, {"administrateur"}),
    ("GET", "/admin/drift", None, {"administrateur"}),
]


@pytest.mark.parametrize("method,path,body,allowed", NEW_ENDPOINTS)
def test_s1_new_endpoints_role_matrix(env, method, path, body, allowed):
    client, _ = env
    for uid in (1, 2, 3, 4):
        r = client.request(method, path, json=body, headers=as_user(uid))
        if USERS[uid]["role"] in allowed:
            assert r.status_code == 200, f"{USERS[uid]['role']} sur {method} {path}: {r.text}"
        else:
            assert r.status_code == 403, f"{USERS[uid]['role']} sur {method} {path}"


@pytest.mark.parametrize("method,path,body,allowed", NEW_ENDPOINTS)
def test_s1_new_endpoints_require_token(env, method, path, body, allowed):
    client, _ = env
    assert client.request(method, path, json=body).status_code == 401


# ---------------- P3-15 : KPI et alertes ----------------

def test_kpis_values(env):
    client, _ = env
    r = client.get("/kpis?jours=30", headers=MANAGER)
    assert r.status_code == 200
    k = r.json()
    assert k["periode_jours"] == 30 and k["factures_scorees"] == 10
    assert k["taux_alerte"] == 0.4
    assert k["precision"] == pytest.approx(2 / 3, abs=1e-4)
    assert k["montant_economise"] == 150000
    assert k["par_jour"] == [{"jour": "2026-10-15", "factures": 4, "alertes": 1}]
    assert k["regles"] == [{"regle_code": "ORDONNANCE_REUTILISEE", "n": 2}]


@pytest.mark.parametrize("query", ["jours=0", "jours=400", "jours=abc"])
def test_kpis_rejects_bad_period(env, query):
    client, _ = env
    assert client.get(f"/kpis?{query}", headers=MANAGER).status_code == 422


def test_alert_list_has_total_count_and_rule_count(env):
    client, _ = env
    r = client.get("/alerts", headers=MANAGER)
    assert r.status_code == 200
    assert r.headers["x-total-count"] == "3"
    assert r.json()[0]["nb_regles"] == 2


def test_alert_detail_includes_shap_slot_and_rules(env):
    client, _ = env
    r = client.get("/alerts/FAC-00000001", headers=MANAGER)
    assert r.status_code == 200
    body = r.json()
    assert body["regles"][0]["regle_code"] == "QUANTITE_ANORMALE"
    assert {"prediction", "shap", "decisions", "regles"} <= set(body)


# ---------------- P3-16 : règles de prescription stockées avec l'alerte ----------------

def _medicament_sans_ordonnance():
    p = valid()
    p["type_facture"] = "PHARMACIE"
    p["lignes"] = [{"code": "MED-PARA500", "type_ligne": "MEDICAMENT", "quantite": 2,
                    "prix_unitaire": 1200}]
    return p


def test_prescription_rule_is_stored_audited_and_returned(env):
    client, holder = env
    r = client.post("/predict", json=_medicament_sans_ordonnance(), headers=MANAGER)
    assert r.status_code == 200
    assert [x["regle_code"] for x in r.json()["regles"]] == ["MEDICAMENT_SANS_ORDONNANCE"]
    assert holder["conn"].executed("INSERT INTO ALERTES_PRESCRIPTION")
    assert holder["conn"].executed("INSERT INTO EXPLICATIONS_SHAP")
    audit = [a for a in holder["conn"].audits() if a["event_type"] == "prediction"][0]
    assert audit["output"]["regles"] == ["MEDICAMENT_SANS_ORDONNANCE"]


def test_provider_does_not_see_rules(env):
    client, _ = env
    r = client.post("/predict", json=_medicament_sans_ordonnance(), headers=PRO)
    assert r.status_code == 200 and "regles" not in r.json()


def test_clean_invoice_has_no_rule_alert(env):
    client, holder = env
    r = client.post("/predict", json=valid(), headers=MANAGER)
    assert r.status_code == 200 and r.json()["regles"] == []
    assert not holder["conn"].executed("INSERT INTO ALERTES_PRESCRIPTION")


# ---------------- P3-17 : seuil, versions, activation, retour arrière, audit ----------------

def test_threshold_read_and_update_is_audited(env):
    client, holder = env
    assert client.get("/admin/threshold", headers=ADMIN).json()["seuil"] == 0.8
    r = client.put("/admin/threshold", json={"seuil": 0.75}, headers=ADMIN)
    assert r.status_code == 200 and r.json() == {"seuil": 0.75, "ancien_seuil": 0.8}
    audit = [a for a in holder["conn"].audits() if a["event_type"] == "seuil_modifie"][0]
    assert audit["input"] == {"ancien_seuil": 0.8, "nouveau_seuil": 0.75}
    assert audit["actor"] == 4


@pytest.mark.parametrize("body", [{"seuil": 0}, {"seuil": 1}, {"seuil": 1.5}, {"seuil": -0.2},
                                  {"seuil": "abc"}, {}])
def test_threshold_rejects_invalid_values(env, body):
    client, holder = env
    assert client.put("/admin/threshold", json=body, headers=ADMIN).status_code == 422
    assert holder["conn"].config["seuil_alerte"] == "0.8"      # rien n'a changé


def test_threshold_change_is_immediate_on_next_predict(env):
    """Critère P3-17 : changement de seuil immédiat."""
    client, _ = env
    client.put("/admin/threshold", json={"seuil": 0.95}, headers=ADMIN)
    r = client.post("/predict", json=valid(), headers=MANAGER)       # score fixe 0.9
    assert r.json()["seuil"] == 0.95 and r.json()["is_alert"] is False
    p = valid()
    p["facture_id"] = "FAC-00000003"
    client.put("/admin/threshold", json={"seuil": 0.5}, headers=ADMIN)
    r = client.post("/predict", json=p, headers=MANAGER)
    assert r.json()["seuil"] == 0.5 and r.json()["is_alert"] is True


def test_model_versions_listing(env):
    client, _ = env
    body = client.get("/admin/model/versions", headers=ADMIN).json()
    assert body["actuelle"] == "7"
    assert [v["version"] for v in body["versions"]] == ["7", "6"]


def test_model_versions_502_when_mlflow_down(env):
    client, holder = env
    holder["registry"].fail = True
    assert client.get("/admin/model/versions", headers=ADMIN).status_code == 502


def test_activate_version_is_audited(env):
    client, holder = env
    r = client.post("/admin/model/activate", json={"version": "6"}, headers=ADMIN)
    assert r.status_code == 200
    assert r.json() == {"name": "predicare-fraud", "version": "6", "previous_version": "7"}
    audit = [a for a in holder["conn"].audits() if a["event_type"] == "modele_charge"][0]
    assert audit["input"]["action"] == "activate" and audit["output"] == {"active_version": "6"}


@pytest.mark.parametrize("version", ["abc", "", "1; DROP", "-1", "1234567"])
def test_activate_rejects_bad_version(env, version):
    client, _ = env
    assert client.post("/admin/model/activate", json={"version": version},
                       headers=ADMIN).status_code == 422


def test_activate_failure_keeps_old_model_and_writes_no_audit(env):
    client, holder = env
    holder["registry"].fail = True
    assert client.post("/admin/model/activate", json={"version": "6"},
                       headers=ADMIN).status_code == 502
    assert holder["registry"].get().version == "7"
    assert not [a for a in holder["conn"].audits() if a["event_type"] == "modele_charge"]


def test_rollback_restores_previous_version(env):
    client, holder = env
    r = client.post("/admin/model/rollback", headers=ADMIN)
    assert r.status_code == 200 and r.json()["version"] == "6"
    audit = [a for a in holder["conn"].audits() if a["event_type"] == "modele_charge"][0]
    assert audit["input"]["action"] == "rollback"


def test_rollback_without_history_is_409(env):
    client, holder = env
    holder["conn"].model_history = []
    assert client.post("/admin/model/rollback", headers=ADMIN).status_code == 409


def test_audit_log_is_readable_by_admin_only_and_validated(env):
    client, _ = env
    r = client.get("/admin/audit?type_evenement=prediction&limit=10", headers=ADMIN)
    assert r.status_code == 200 and r.json()[0]["type_evenement"] == "prediction"
    assert client.get("/admin/audit?type_evenement=DROP TABLE", headers=ADMIN).status_code == 422
    assert client.get("/admin/audit?limit=500", headers=ADMIN).status_code == 422
    assert client.get("/admin/audit", headers=MANAGER).status_code == 403


# ---------------- P3-18 / P3-19 : supervision ----------------

def test_metrics_endpoint(env):
    client, _ = env
    client.get("/admin/ping", headers=ADMIN)
    client.get("/admin/ping", headers=MANAGER)                       # un 403 compté en 4xx
    m = client.get("/admin/metrics", headers=ADMIN).json()
    assert m["http"]["requetes_total"] >= 2 and m["http"]["erreurs_4xx"] >= 1
    assert "GET /admin/ping" in m["http"]["routes"]
    assert m["predictions_24h"] == {"volume": 10, "alertes": 2, "taux_alerte": 0.2,
                                    "latence_ms": {"p50": 12.0, "p95": 40.0, "max": 55}}
    assert m["evenements_24h"]["factures_rejetees"] == 3
    assert m["modele"]["version"] == "7"


def test_metrics_use_route_template_not_raw_url(env):
    client, _ = env
    client.get("/alerts/FAC-00000001", headers=MANAGER)
    routes = client.get("/admin/metrics", headers=ADMIN).json()["http"]["routes"]
    assert "GET /alerts/{facture_id}" in routes
    assert not any("FAC-00000001" in k for k in routes)


def test_drift_reports_strong_drift(env):
    """Critère P3-19 : valeur de dérive affichée."""
    client, _ = env
    d = client.get("/admin/drift", headers=ADMIN).json()
    assert d["variables_suivies"] == ["x", "y"]
    assert d["statut"] == "forte" and d["psi_max"] > 0.25
    by = {v["variable"]: v for v in d["variables"]}
    assert by["x"]["niveau"] == "forte" and by["y"]["niveau"] == "stable"


def test_drift_not_enough_data(env):
    client, holder = env
    holder["conn"].n_drift = 5
    d = client.get("/admin/drift", headers=ADMIN).json()
    assert d["statut"] == "donnees_insuffisantes" and d["psi_max"] is None


# ---------------- P3-20 : support du frontend ----------------

def test_cors_exposes_headers_the_front_needs(env):
    client, _ = env
    r = client.get("/admin/ping", headers={**ADMIN, "Origin": "http://localhost:3000"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    exposed = r.headers["access-control-expose-headers"]
    assert "X-Total-Count" in exposed and "X-Request-ID" in exposed and "Retry-After" in exposed


def test_cors_preflight_for_authorized_json_request(env):
    client, _ = env
    r = client.options("/predict", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type"})
    assert r.status_code == 200
    assert "POST" in r.headers["access-control-allow-methods"]


def test_unknown_origin_gets_no_cors_header(env):
    client, _ = env
    r = client.get("/admin/ping", headers={**ADMIN, "Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_request_id_is_generated_and_echoed(env):
    client, _ = env
    assert client.get("/admin/ping", headers=ADMIN).headers["x-request-id"]
    r = client.get("/admin/ping", headers={**ADMIN, "X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"


def test_unexpected_error_returns_clean_json_500(env, monkeypatch):
    client, _ = env
    monkeypatch.setattr("api.routers.kpis.repo.kpi_summary",
                        lambda conn, jours: (_ for _ in ()).throw(RuntimeError("secret interne")))
    safe = TestClient(app, raise_server_exceptions=False)
    r = safe.get("/kpis", headers=MANAGER)
    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == "Erreur interne du serveur" and body["request_id"]
    assert "secret interne" not in r.text                              # pas de fuite de détail


def test_error_formats_are_consistent(env):
    """Toutes les erreurs portent un champ `detail` (texte) ; 422 ajoute `errors` ou `codes`."""
    client, _ = env
    r401 = client.get("/kpis")
    r403 = client.get("/kpis", headers=PRO)
    r422 = client.get("/kpis?jours=0", headers=MANAGER)
    for r in (r401, r403, r422):
        assert isinstance(r.json()["detail"], str)
    assert r422.json()["errors"][0]["field"].endswith("jours")
