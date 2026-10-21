"""Explicateur HGB : la valeur de base est le score moyen d'un fond légitime."""
import sys
from pathlib import Path

ML_DIR = Path(__file__).resolve().parents[1]
BACKEND = ML_DIR.parent
for _p in (str(BACKEND), str(ML_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import types

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier

from api.services.hgb_explainer import HGBPermutationExplainer

FEATURES = ["x", "z", "kind"]
CATEGORIES = {"kind": ["A", "B"]}


def _model_and_data():
    rng = np.random.RandomState(0)
    df = pd.DataFrame({"x": rng.rand(200), "z": rng.rand(200), "kind": rng.choice(["A", "B"], 200)})
    df["kind"] = pd.Categorical(df["kind"], categories=CATEGORIES["kind"])
    y = (df["x"] > 0.7).astype(int)
    model = HistGradientBoostingClassifier(
        categorical_features="from_dtype", max_iter=30, random_state=0
    ).fit(df, y)
    return model, df


def _fake_shap():
    class PermutationExplainer:
        def __init__(self, fn, masker, feature_names=None):
            self.fn, self.masker = fn, np.asarray(masker)

    return types.SimpleNamespace(PermutationExplainer=PermutationExplainer)


def test_base_est_le_score_moyen_du_fond(monkeypatch):
    monkeypatch.setitem(sys.modules, "shap", _fake_shap())
    model, df = _model_and_data()
    explainer = HGBPermutationExplainer(model, df.head(30), FEATURES, CATEGORIES, max_background=10)
    background = df.head(10)
    assert np.allclose(explainer.expected_value, model.predict_proba(background).mean(axis=0))
    # et non le score de la première ligne seulement (ancien comportement)
    assert not np.isclose(explainer.expected_value[-1], model.predict_proba(df.head(1))[0, 1])
    assert explainer._explainer.masker.shape == (10, 3)  # fond plafonné


def test_additivite_avec_le_vrai_shap():
    pytest.importorskip("shap")
    model, df = _model_and_data()
    explainer = HGBPermutationExplainer(model, df.head(20), FEATURES, CATEGORIES)
    row = df.iloc[[150]]
    values = np.asarray(explainer.shap_values(row))[0]
    values = values[..., -1] if values.ndim == 2 else values
    reconstructed = explainer.expected_value[-1] + values.sum()
    assert abs(reconstructed - model.predict_proba(row)[0, 1]) < 1e-3
