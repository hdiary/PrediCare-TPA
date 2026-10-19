"""P3-23 : lot de 20 factures (valides, invalides, inédites) -> rejet propre, jamais de 500.

Deux niveaux :
  - validation seule (sans FastAPI) : chaque cas produit exactement les codes attendus ;
  - API complète : statut HTTP attendu, aucune insertion pour un rejet, audit du rejet.
Les jeux de données sont dans tests/data/lot_20_factures.json (modifiable sans toucher au code).
"""
import json
import pathlib
from datetime import date

import pytest
from test_predict_flow import setup

LOT = json.loads((pathlib.Path(__file__).parent / "data" / "lot_20_factures.json").read_text("utf-8"))
IDS = [c["nom"] for c in LOT]


class LotConn:
    """Base minimale : mêmes référentiels connus que les autres tests."""

    class _Cur:
        def __init__(self, row=None, rows=None):
            self.row, self.rows = row, rows or []

        def fetchone(self):
            return self.row

        def fetchall(self):
            return self.rows

    def execute(self, query, params=()):
        q = " ".join(query.split()).upper()
        C = self._Cur
        if "SELECT 1 AS X FROM ASSURES" in q:
            return C({"x": 1} if params[0] == "ASS-9CAA1484E0" else None)
        if "SELECT 1 AS X FROM PRESTATAIRES" in q:
            return C({"x": 1} if params[0] == "PRE-00214" else None)
        if "FROM GARANTIES" in q:
            return C({"x": 1})
        if "FROM REFERENTIEL_ACTES" in q:
            known = {"CONS-GEN": "ACTE", "MED-PARA500": "MEDICAMENT"}
            return C(rows=[{"code": c, "type_ligne": known[c], "libelle": "Libellé"}
                           for c in params[0] if c in known])
        return C(None)


def test_lot_has_exactly_20_cases():
    assert len(LOT) == 20
    assert len({c["facture"]["facture_id"] for c in LOT}) == 20   # identifiants tous distincts


@pytest.mark.parametrize("case", LOT, ids=IDS)
def test_validation_level(case):
    from api.validation import validate_invoice

    if case.get("doublon"):
        pytest.skip("doublon : détecté dans la route /predict (testé au niveau API)")
    erreurs, clean = validate_invoice(case["facture"], LotConn())
    codes = sorted({e["code"] for e in erreurs})
    assert codes == case["attendu_codes"], case["nom"]
    assert (clean is not None) == (case["attendu_http"] == 200)


def test_future_date_uses_real_today():
    from api.validation import validate_structure

    erreurs, _ = validate_structure(LOT[7]["facture"], today=date(2026, 10, 17))
    assert [e["code"] for e in erreurs] == ["DATE_FUTURE"]


# ---------- niveau API ----------

@pytest.mark.parametrize("case", LOT, ids=IDS)
def test_api_level(case, setup):
    from test_predict_flow import manager

    client, holder = setup
    holder["conn"].existing_invoice = bool(case.get("doublon"))
    r = client.post("/predict", json=case["facture"], headers=manager())
    assert r.status_code == case["attendu_http"], f"{case['nom']} -> {r.status_code} {r.text}"
    if case["attendu_http"] == 200:
        assert r.json()["accepte"] is True
    else:
        assert sorted(r.json()["codes"]) == case["attendu_codes"]
        assert not holder["conn"].executed("INSERT INTO FACTURES")
        assert [a["event_type"] for a in holder["conn"].audits()] == ["facture_rejetee"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"facture_id": "FAC-1'; DROP TABLE factures;--"},
        {"facture_id": "x" * 100000},
        {"lignes": "pas une liste"},
        {"lignes": [None, 3, "a"]},
        {"facture_id": None, "assure_id": 12, "devise": ["MGA"]},
    ],
)
def test_hostile_payloads_never_cause_500(payload, setup):
    from test_predict_flow import manager

    client, _ = setup
    r = client.post("/predict", json=payload, headers=manager())
    assert r.status_code == 422
    assert "codes" in r.json()


def test_non_object_body_is_422(setup):
    from test_predict_flow import manager

    client, _ = setup
    r = client.post("/predict", json=[1, 2, 3], headers=manager())
    assert r.status_code == 422
