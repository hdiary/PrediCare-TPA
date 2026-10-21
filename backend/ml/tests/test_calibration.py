from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import calibration  # noqa: E402
import predict  # noqa: E402
import train  # noqa: E402


class MarginModel:
    def decision_function(self, features):
        return features["margin"].to_numpy()

    def predict_proba(self, features):
        positive = 1 / (1 + np.exp(-self.decision_function(features)))
        return np.column_stack([1 - positive, positive])


class FixedCalibrator:
    def predict_proba(self, margins):
        positive = np.where(margins[:, 0] > 0, 0.9, 0.1)
        return np.column_stack([1 - positive, positive])


def test_calibrator_sigmoide_produit_des_probabilites_monotones():
    model = MarginModel()
    features = pd.DataFrame({"margin": np.linspace(-3, 3, 60)})
    labels = (features["margin"] > 0).astype(int)

    fitted = calibration.fit_sigmoid_calibrator(model, features, labels)
    scores = calibration.calibrated_probability(model, fitted, features)

    assert np.all(np.diff(scores) >= 0)
    assert np.all((scores >= 0) & (scores <= 1))
    assert scores[0] < 0.1
    assert scores[-1] > 0.9


def test_calibrateur_refuse_une_seule_classe():
    with pytest.raises(ValueError, match="les deux classes"):
        calibration.fit_sigmoid_calibrator(
            MarginModel(),
            pd.DataFrame({"margin": [0.1, 0.2]}),
            [0, 0],
        )


def test_calibrateur_produit_le_score_utilise_par_predict():
    original = predict._ART
    predict._ART = {
        "model": MarginModel(),
        "calibrator": FixedCalibrator(),
        "features": ["margin"],
        "seuil": 0.8,
        "version": "calibrated-test",
        "categories": {},
    }
    try:
        result = predict.score(pd.DataFrame({"margin": [-1.0, 1.0]}))
    finally:
        predict._ART = original

    assert result["score"].tolist() == pytest.approx([0.1, 0.9])
    assert result["alerte"].tolist() == [False, True]


def test_decoupage_temporel_reserve_cinq_fenetres():
    dates = pd.Series(pd.date_range("2026-01-01", periods=100, freq="D"))
    windows = train.temporal_split(dates)

    assert len(windows) == 5
    assert all(len(window) > 0 for window in windows)
    assert all(
        dates.iloc[left].max() < dates.iloc[right].min()
        for left, right in zip(windows, windows[1:])
    )
