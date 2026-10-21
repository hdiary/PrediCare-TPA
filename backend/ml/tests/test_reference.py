"""Fond SHAP : uniquement des factures légitimes, JSON strict."""
import sys
from pathlib import Path

ML_DIR = Path(__file__).resolve().parents[1]
BACKEND = ML_DIR.parent
for _p in (str(BACKEND), str(ML_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json

import numpy as np
import pandas as pd
import pytest

from reference import reference_rows


def _data(n=100):
    rng = np.random.RandomState(1)
    X = pd.DataFrame({
        "id": np.arange(n),
        "montant": rng.rand(n) * 1000,
        "ratio": np.where(np.arange(n) % 7 == 0, np.nan, rng.rand(n)),
        "infini": np.where(np.arange(n) % 11 == 0, np.inf, 1.0),
        "flag": (np.arange(n) % 2 == 0),
        "type": pd.Categorical(np.where(np.arange(n) % 5 == 0, None, "A"), categories=["A", "B"]),
    })
    y = pd.Series((np.arange(n) % 4 == 0).astype(int))
    return X, y


def test_uniquement_des_factures_legitimes_et_json_strict():
    X, y = _data()
    rows = reference_rows(X, y, n=25, seed=3)
    assert len(rows) == 25
    assert all(y.iloc[r["id"]] == 0 for r in rows)
    json.dumps({"rows": rows}, allow_nan=False)  # ni NaN ni Infinity
    assert any(r["ratio"] is None for r in rows) or any(r["type"] is None for r in rows)


def test_ordre_des_colonnes_et_plafond():
    X, y = _data(30)
    rows = reference_rows(X, y, n=500, features=["type", "montant"])
    assert len(rows) == int((y == 0).sum())
    assert list(rows[0]) == ["type", "montant"]


def test_sans_facture_legitime():
    X, y = _data(10)
    with pytest.raises(ValueError):
        reference_rows(X, pd.Series(np.ones(10, dtype=int)))
