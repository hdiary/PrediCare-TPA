"""Seuil de décision lu avec le modèle (predict.py : repli sur le .env uniquement si absent)."""
import sys
from pathlib import Path

ML_DIR = Path(__file__).resolve().parents[1]
BACKEND = ML_DIR.parent
for _p in (str(BACKEND), str(ML_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from datetime import datetime

from api.services.model_types import ModelBundle, decision_threshold


def _bundle(metadata):
    return ModelBundle(name="m", version="v", model=None, explainer=None, feature_names=[],
                       loaded_at=datetime.now(), metadata=metadata)


def test_seuil_du_modele():
    assert decision_threshold(_bundle({"decision_threshold": 0.9678})) == 0.9678
    assert decision_threshold(_bundle({"decision_threshold": "0.9999"})) == 0.9999


def test_seuil_absent_ou_invalide_donne_none():
    for metadata in ({}, {"decision_threshold": None}, {"decision_threshold": "abc"},
                     {"decision_threshold": 0}, {"decision_threshold": 1.5},
                     {"decision_threshold": float("nan")}, None):
        assert decision_threshold(_bundle(metadata)) is None


def test_repli_sur_la_configuration():
    # même expression que dans predict.py : `decision_threshold(bundle) or settings.alert_threshold`
    assert (decision_threshold(_bundle({})) or 0.8) == 0.8
    assert (decision_threshold(_bundle({"decision_threshold": 0.9999})) or 0.8) == 0.9999
