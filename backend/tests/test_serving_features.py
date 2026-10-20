import pandas as pd
import pytest

from api.services.features import FeatureMismatchError, build_features
from ml import preprocess


def test_database_string_numeric_features_are_converted(monkeypatch):
    def build(_payload, _conn):
        return pd.DataFrame(
            {
                "montant_total": ["1500.5"],
                "nb_lignes": ["2"],
                "type_facture": ["CONSULTATION"],
            },
            index=["FAC-90000001"],
        )

    monkeypatch.setattr(preprocess, "build_features", build)

    result = build_features(
        {"facture_id": "FAC-90000001"},
        conn=None,
        expected=["montant_total", "nb_lignes", "type_facture"],
    )

    assert pd.api.types.is_numeric_dtype(result["montant_total"])
    assert pd.api.types.is_numeric_dtype(result["nb_lignes"])
    assert isinstance(result["type_facture"].dtype, pd.CategoricalDtype)
    assert result.loc["FAC-90000001", "montant_total"] == 1500.5


def test_invalid_numeric_feature_reports_a_feature_mismatch(monkeypatch):
    def build(_payload, _conn):
        return pd.DataFrame(
            {"montant_total": ["not-a-number"]},
            index=["FAC-90000001"],
        )

    monkeypatch.setattr(preprocess, "build_features", build)

    with pytest.raises(FeatureMismatchError, match="montant_total"):
        build_features(
            {"facture_id": "FAC-90000001"},
            conn=None,
            expected=["montant_total"],
        )
