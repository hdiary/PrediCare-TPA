"""Tests de predict (validation des entrées, version) et du registre (retour arrière)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import predict  # noqa: E402
import registry  # noqa: E402


class FauxModele:
    def predict_proba(self, X):
        p = np.clip(X["montant"].fillna(0).values / 100, 0, 1)
        return np.column_stack([1 - p, p])


@pytest.fixture
def art(monkeypatch):
    a = {"model": FauxModele(), "features": ["montant", "type"], "seuil": 0.5,
         "version": "test-v1", "categories": {"type": ["A", "B"]}}
    monkeypatch.setattr(predict, "_ART", a)
    return a


def test_score_et_version(art):
    X = pd.DataFrame({"montant": [10, 90], "type": ["A", "B"]}, index=["F1", "F2"])
    r = predict.score(X)
    assert list(r["alerte"]) == [False, True]
    assert set(r["model_version"]) == {"test-v1"}  # exigence journal d'audit


def test_seuil_modifiable_en_direct(art):
    X = pd.DataFrame({"montant": [30], "type": ["A"]})
    assert not predict.score(X)["alerte"].iloc[0]
    assert predict.score(X, seuil=0.2)["alerte"].iloc[0]


def test_colonne_manquante_message_clair(art):
    with pytest.raises(predict.EntreeInvalide, match="montant"):
        predict.score(pd.DataFrame({"type": ["A"]}))


def test_lot_vide(art):
    with pytest.raises(predict.EntreeInvalide):
        predict.score(pd.DataFrame({"montant": [], "type": []}))


def test_pas_un_dataframe(art):
    with pytest.raises(predict.EntreeInvalide):
        predict.score([1, 2, 3])


def test_valeurs_absurdes_ne_plantent_pas(art):
    X = pd.DataFrame({"montant": ["abc", np.inf, None], "type": ["Z", None, "A"]})
    r = predict.score(X)  # texte, infini, manquant, catégorie inconnue
    assert len(r) == 3 and r["score"].between(0, 1).all()


def test_registre_bascule_et_retour_arriere(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(registry, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(registry, "ACTIVE", tmp_path / "model_active.joblib")
    for v in ("v1", "v2"):
        (tmp_path / f"model_{v}.joblib").write_text(v)
        registry.register({"version": v, "file": f"model_{v}.joblib",
                           "trained_at": "2026-10-16", "test": {}})
    assert registry.active_version() == "v2"
    assert (tmp_path / "model_active.joblib").read_text() == "v2"
    registry.set_active("v1")  # retour arrière
    assert registry.active_version() == "v1"
    assert (tmp_path / "model_active.joblib").read_text() == "v1"
    assert {v["version"]: v["status"] for v in registry.versions()} == {"v1": "active", "v2": "archived"}


def test_version_inconnue(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(registry, "REGISTRY", tmp_path / "registry.json")
    with pytest.raises(KeyError):
        registry.set_active("fantome")
