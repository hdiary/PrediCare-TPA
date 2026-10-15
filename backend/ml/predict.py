"""Inférence : score une ou plusieurs factures avec le modèle actif.

Les features « de groupe » (doublons, ordonnance réutilisée, volume prestataire)
ont besoin de l'historique : à l'inférence, calculez-les sur la base complète
(factures déjà reçues + nouvelle facture), puis gardez la ligne de la nouvelle facture.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

MODELS_DIR = Path(__file__).resolve().parent / "models"
_ART = None


def load(path: str | Path | None = None) -> dict:
    global _ART
    if _ART is None or path:
        _ART = joblib.load(path or MODELS_DIR / "model_active.joblib")
    return _ART


def score(X: pd.DataFrame, seuil: float | None = None) -> pd.DataFrame:
    """X : sortie de features.build_features (colonnes identiques à l'entraînement)."""
    art = load()
    X = X[art["features"]]
    for c, cats in art["categories"].items():
        X[c] = pd.Categorical(X[c], categories=cats)
    p = art["model"].predict_proba(X)[:, 1]
    s = art["seuil"] if seuil is None else seuil  # seuil modifiable en direct (admin)
    return pd.DataFrame({"score": p, "alerte": p >= s}, index=X.index)
