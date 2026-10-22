"""Probability calibration helpers shared by training and API inference."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression


def model_margin(model, features) -> np.ndarray:
    """Return an unclipped one-dimensional score suitable for sigmoid calibration."""
    if getattr(model, "booster_", None) is not None:
        return np.asarray(model.predict(features, raw_score=True), dtype=float).reshape(-1)
    if callable(getattr(model, "get_booster", None)):
        return np.asarray(model.predict(features, output_margin=True), dtype=float).reshape(-1)
    if callable(getattr(model, "decision_function", None)):
        return np.asarray(model.decision_function(features), dtype=float).reshape(-1)

    probabilities = np.asarray(model.predict_proba(features), dtype=float)
    positive = np.clip(probabilities[:, 1], 1e-12, 1 - 1e-12)
    return np.log(positive / (1 - positive))


def fit_sigmoid_calibrator(model, features, labels) -> LogisticRegression:
    labels = np.asarray(labels, dtype=int)
    if np.unique(labels).size != 2:
        raise ValueError("La fenêtre de calibration doit contenir les deux classes.")
    margins = model_margin(model, features).reshape(-1, 1)
    if len(margins) != len(labels) or not np.isfinite(margins).all():
        raise ValueError("Les scores bruts de calibration sont invalides.")
    return LogisticRegression(C=1e6, max_iter=1000).fit(margins, labels)


def calibrated_probability(model, calibrator, features) -> np.ndarray:
    """Use the stored sigmoid calibrator, or preserve legacy model probabilities."""
    if calibrator is None:
        return np.asarray(model.predict_proba(features), dtype=float)[:, 1]

    margins = model_margin(model, features).reshape(-1, 1)
    probabilities = np.asarray(calibrator.predict_proba(margins), dtype=float)[:, 1]
    if not np.isfinite(probabilities).all() or (
        (probabilities < 0) | (probabilities > 1)
    ).any():
        raise ValueError("Le calibrateur a produit un score hors de [0, 1].")
    return probabilities
