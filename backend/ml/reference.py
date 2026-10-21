"""Lignes de référence (fond) des explications SHAP : factures LÉGITIMES du jeu d'entraînement.

Sans fond représentatif, la « valeur de base » SHAP n'a pas de sens métier. Ces lignes sont
écrites dans reference_sample.json (voir api/model_seed.py et make_reference_sample.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

N_REFERENCE = 25


def _clean(value):
    """Valeur JSON sûre : manquant/infini -> None, types numpy -> types Python."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (bool, np.bool_)):
        return float(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, str):
        return value
    return None if pd.isna(value) else str(value)


def reference_rows(X: pd.DataFrame, y: pd.Series, n: int = N_REFERENCE, seed: int = 42,
                   features: list[str] | None = None) -> list[dict]:
    """n factures non frauduleuses tirées au hasard dans X (à appeler sur la fenêtre d'entraînement)."""
    legit = X[(np.asarray(y) == 0)]
    if legit.empty:
        raise ValueError("Aucune facture légitime pour construire l'échantillon de référence")
    sample = legit.sample(n=min(n, len(legit)), random_state=seed)
    columns = list(features) if features else list(X.columns)
    return [
        {name: _clean(value) for name, value in record.items()}
        for record in sample[columns].to_dict("records")
    ]
