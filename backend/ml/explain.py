"""Explications SHAP : top 5 des facteurs par alerte (nécessite `shap`).

Fonctionne avec LightGBM / XGBoost (TreeExplainer). Pour le modèle sklearn `hgb`,
utilisez plutôt LightGBM en production : shap ne supporte pas HistGradientBoosting.
"""
from __future__ import annotations

import pandas as pd

import predict


def top_facteurs(X: pd.DataFrame, k: int = 5) -> dict[str, list[tuple[str, float]]]:
    import shap  # import tardif : dépendance optionnelle
    art = predict.load()
    X = predict.validate(X, art)
    sv = shap.TreeExplainer(art["model"]).shap_values(X)
    if isinstance(sv, list):  # anciennes versions : [classe0, classe1]
        sv = sv[1]
    out = {}
    for i, fid in enumerate(X.index):
        order = abs(sv[i]).argsort()[::-1][:k]
        out[fid] = [(X.columns[j], float(sv[i][j])) for j in order]
    return out
