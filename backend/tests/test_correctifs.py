"""Tests des correctifs : autorisation /predict, longueurs, taille des requêtes, logs, login."""
import json
import logging
import os
from unittest.mock import MagicMock

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "x" * 40)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.db import get_db  # noqa: E402
from api.deps import get_current_user  # noqa: E402
from api.logging_config import JsonFormatter  # noqa: E402
from api.main import app  # noqa: E402
from api.validation import validate_structure  # noqa: E402

FACTURE = {
    "facture_id": "FAC-90000001", "numero_facture": "PRE214/2026/00001",
    "prestataire_id": "PRE-00214", "assure_id": "ASS-9CAA1484E0", "contrat_id": "CTR-000001",
    "type_facture": "CONSULTATION", "date_soin": "2026-10-10", "heure_soin": "09:30",
    "devise": "MGA",
    "lignes": [{"code": "CONS-GEN", "type_ligne": "ACTE", "quantite": 1, "prix_unitaire": 25000}],
}


@pytest.fixture
def conn():
    return MagicMock()


@pytest.fixture
def client(conn):
    app.dependency_overrides[get_db] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def _login_as(role, prestataire_id=None):
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": 7, "email": "u@test", "role": role, "assure_id": None,
        "prestataire_id": prestataire_id, "is_active": True,
    }


def _audits(conn):
    return [c for c in conn.execute.call_args_list if "journal_audit" in str(c.args[0])]


# ---------- autorisation /predict ----------

def test_pro_ne_peut_pas_soumettre_pour_un_autre_prestataire(client, conn):
    _login_as("professionnel_sante", "PRE-00999")
    r = client.post("/predict", json=FACTURE)            # facture au nom de PRE-00214
    assert r.status_code == 403
    assert r.json()["codes"] == ["PRESTATAIRE_NON_AUTORISE"]
    assert len(_audits(conn)) == 1                        # le refus est tracé
    conn.commit.assert_called()


def test_pro_sans_prestataire_rattache_est_refuse(client):
    _login_as("professionnel_sante", None)
    assert client.post("/predict", json=FACTURE).status_code == 403


def test_pro_pour_son_propre_prestataire_passe_l_autorisation(client):
    _login_as("professionnel_sante", "PRE-00214")
    assert client.post("/predict", json=FACTURE).status_code != 403


def test_gestionnaire_non_limite_par_prestataire(client):
    _login_as("gestionnaire")
    assert client.post("/predict", json=FACTURE).status_code != 403


def test_assure_reste_interdit(client):
    _login_as("assure")
    assert client.post("/predict", json=FACTURE).status_code == 403


# ---------- longueurs ----------

@pytest.mark.parametrize("champ", ["numero_facture"])
def test_texte_trop_long_rejete(champ):
    erreurs, _ = validate_structure({**FACTURE, champ: "X" * 65})
    assert any(e["code"] == "VALEUR_INVALIDE" and e["champ"] == champ for e in erreurs)


def test_numero_facture_normal_accepte():
    erreurs, _ = validate_structure(FACTURE)
    assert erreurs == []


def test_code_ligne_trop_long_rejete():
    ligne = {"code": "A" * 41, "quantite": 1, "prix_unitaire": 1}
    erreurs, _ = validate_structure({**FACTURE, "lignes": [ligne]})
    assert any(e["champ"] == "lignes[1].code" for e in erreurs)


# ---------- taille des requêtes ----------

def test_corps_trop_volumineux_413(client):
    r = client.post("/auth/login", content=b"x" * 2_000_000,
                    headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_corps_normal_non_bloque(client):
    r = client.post("/auth/login", json={"email": "a@b.c", "password": "x"})
    assert r.status_code != 413


# ---------- login par formulaire ----------

def test_token_mot_de_passe_geant_refuse_sans_toucher_la_base(client, conn):
    r = client.post("/auth/token", data={"username": "a@b.c", "password": "p" * 5000})
    assert r.status_code == 401
    conn.execute.assert_not_called()


# ---------- journaux ----------

def _format(**kw):
    rec = logging.LogRecord("t", logging.WARNING, "f.py", 1, kw.pop("msg", "m"), (), None)
    for k, v in kw.items():
        setattr(rec, k, v)
    return json.loads(JsonFormatter().format(rec))     # lève si le JSON est invalide


def test_logs_contiennent_les_champs_extra():
    out = _format(msg="login_ok", user_id=3, role="gestionnaire")
    assert out["user_id"] == 3 and out["role"] == "gestionnaire" and out["level"] == "WARNING"


def test_logs_json_valide_avec_guillemets_et_accents():
    out = _format(msg='erreur "grave" : donnée\nsur deux lignes')
    assert 'donnée' in out["msg"]
