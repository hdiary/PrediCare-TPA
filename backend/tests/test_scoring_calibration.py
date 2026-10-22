from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from api.services.model_types import ModelBundle  # noqa: E402
from api.services.scoring import predict_with_explanation  # noqa: E402


class _Model:
    def decision_function(self, features):
        return features["margin"].to_numpy()

    def predict_proba(self, features):
        positive = 1 / (1 + np.exp(-self.decision_function(features)))
        return np.column_stack((1 - positive, positive))


class _Calibrator:
    def predict_proba(self, margins):
        positive = np.where(margins[:, 0] > 0, 0.9, 0.1)
        return np.column_stack((1 - positive, positive))


class _Explainer:
    expected_value = np.array([0.5, 0.5])

    def shap_values(self, features):
        return np.zeros((len(features), len(features.columns), 2))


def test_api_retourne_le_score_calibre():
    bundle = ModelBundle(
        name="test",
        version="test-calibrated",
        model=_Model(),
        explainer=_Explainer(),
        feature_names=["margin"],
        loaded_at=datetime.now(),
        calibrator=_Calibrator(),
    )

    result = predict_with_explanation(
        bundle,
        pd.DataFrame({"margin": [1.0]}),
        top_k=1,
    )

    assert result["score"] == 0.9
