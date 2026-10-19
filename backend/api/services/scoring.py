"""Score de fraude + valeurs SHAP pour une facture (noms de champs du contrat 11.1)."""
import math

import numpy as np
import pandas as pd

from api.services.model_registry import ModelBundle


def _py(value):
    """Convertit une valeur numpy en type JSON ; NaN -> None."""
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def predict_with_explanation(bundle: ModelBundle, features: pd.DataFrame, top_k: int) -> dict:
    score = float(bundle.model.predict_proba(features)[0][1])

    shap_values = bundle.explainer.shap_values(features)
    if isinstance(shap_values, list):      # certains modèles retournent une liste par classe
        shap_values = shap_values[-1]
    shap_values = np.asarray(shap_values)
    if shap_values.ndim == 3:
        shap_values = shap_values[..., -1]
    row = shap_values[0]

    base = np.ravel(np.asarray(bundle.explainer.expected_value))[-1]
    names = list(features.columns)
    order = np.argsort(-np.abs(row))[:top_k]
    top = [
        {"variable": names[i], "valeur": _py(features.iloc[0, i]), "contribution": float(row[i])}
        for i in order
    ]
    return {
        "score": score,
        "shap": top,
        "shap_complet": {
            "valeur_base": float(base),
            "top": top,
            "toutes": {names[i]: float(row[i]) for i in range(len(names))},
        },
        "variables": {n: _py(features.iloc[0, i]) for i, n in enumerate(names)},
    }
