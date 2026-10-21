import json
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd

from api import model_seed
from api.services import ml_service
from api.services.ml_service import _HGBPermutationExplainer


def test_seed_candidates_keep_active_model_and_include_hgb():
    registry = {
        "active": "lightgbm-active",
        "versions": [
            {"version": "hgb-candidate", "algo": "hgb"},
            {"version": "lightgbm-active", "algo": "lightgbm"},
            {"version": "lightgbm-newer", "algo": "lightgbm"},
        ],
    }

    candidates = model_seed._candidate_versions(registry)

    assert [item["version"] for item in candidates] == [
        "lightgbm-active",
        "hgb-candidate",
    ]


def test_prepare_seed_creates_hgb_archive_alongside_active_model(tmp_path, monkeypatch):
    legacy = tmp_path / "models"
    seed = tmp_path / "models_seed"
    legacy.mkdir()
    entries = [
        {
            "version": "lightgbm-active",
            "file": "model_lightgbm.joblib",
            "algo": "lightgbm",
            "trained_at": "2026-10-18T00:00:00+00:00",
            "test": {},
            "valid": {},
        },
        {
            "version": "hgb-candidate",
            "file": "model_hgb.joblib",
            "algo": "hgb",
            "trained_at": "2026-10-16T00:00:00+00:00",
            "test": {"recall": 0.94},
            "valid": {},
        },
    ]
    (legacy / "registry.json").write_text(
        json.dumps({"active": "lightgbm-active", "versions": entries}),
        encoding="utf-8",
    )
    for entry in entries:
        joblib.dump(
            {"features": ["amount"], "categories": {}, "algo": entry["algo"]},
            legacy / entry["file"],
        )

    monkeypatch.setattr(model_seed, "LEGACY", legacy)
    monkeypatch.setattr(model_seed, "SEED", seed)
    monkeypatch.setattr(model_seed.subprocess, "check_output", lambda *args, **kwargs: "test-commit")

    model_seed.prepare_seed()

    hgb_dir = seed / "vhgb-candidate"
    metadata = json.loads((hgb_dir / "metadata.json").read_text(encoding="utf-8"))
    schema = json.loads((hgb_dir / "feature_schema.json").read_text(encoding="utf-8"))
    assert metadata["algorithm"] == "hgb"
    assert metadata["status"] == "ARCHIVE"
    assert metadata["metrics"]["test"]["recall"] == 0.94
    assert schema["features"] == ["amount"]
    assert (hgb_dir / "model_hgb.joblib").is_file()


class _ModelRegistryConnection:
    def __init__(self):
        self.versions = {"existing-active": "ACTIF"}
        self.inserts = []
        self.commits = 0

    def execute(self, query, params=()):
        if "WHERE version = %s" in query:
            version = params[0]
            row = {"version": version} if version in self.versions else None
            return _Result(row)
        if "WHERE status = 'ACTIF'" in query:
            row = {"version": next(
                (version for version, status in self.versions.items() if status == "ACTIF"),
                None,
            )} if any(status == "ACTIF" for status in self.versions.values()) else None
            return _Result(row)
        if query.startswith("INSERT INTO model_versions"):
            version, _, _, _, status = params[:5]
            self.versions[version] = status
            self.inserts.append(params)
            return None
        raise AssertionError(f"Unexpected query: {query}")

    def commit(self):
        self.commits += 1


class _Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


def test_initialize_syncs_new_seed_without_replacing_active_version(tmp_path, monkeypatch):
    seed = tmp_path / "seed"
    hgb_dir = seed / "vhgb-candidate"
    hgb_dir.mkdir(parents=True)
    artifact_name = "model_hgb.joblib"
    (hgb_dir / artifact_name).write_bytes(b"artifact")
    metadata = {
        "version": "hgb-candidate",
        "artifact": artifact_name,
        "sha256": "test-hash",
        "metrics": {},
        "status": "ARCHIVE",
        "trained_at": "2026-10-16T00:00:00+00:00",
    }
    (hgb_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    store = tmp_path / "store"
    connection = _ModelRegistryConnection()
    registry = ml_service.ModelRegistry()
    monkeypatch.setattr(ml_service, "_SEED_DIRECTORY", seed)
    monkeypatch.setattr(registry, "_store", lambda: store)
    monkeypatch.setattr(registry, "load_active", lambda conn, force=False: "active-bundle")

    assert registry.initialize(connection) == "active-bundle"
    assert registry.initialize(connection) == "active-bundle"

    assert connection.versions == {
        "existing-active": "ACTIF",
        "hgb-candidate": "ARCHIVE",
    }
    assert len(connection.inserts) == 1
    assert connection.commits == 1
    assert (store / "vhgb-candidate" / artifact_name).read_bytes() == b"artifact"


def test_hgb_explainer_supports_categorical_features():
    class _Classifier:
        def predict_proba(self, frame):
            score = (
                frame["amount"].to_numpy(dtype=float)
                + frame["kind"].cat.codes.to_numpy(dtype=float)
            ) / 4
            return np.column_stack((1 - score, score))

    categories = {"kind": ["low", "high"]}
    reference = pd.DataFrame({
        "amount": [0.0, 1.0],
        "kind": pd.Categorical(["low", "high"], categories=categories["kind"]),
    })
    explainer = _HGBPermutationExplainer(
        _Classifier(), reference, ["amount", "kind"], categories
    )

    upload_features = pd.DataFrame({"amount": ["0.0"], "kind": ["low"]})
    values = np.asarray(explainer.shap_values(upload_features))

    assert values.shape == (1, 2, 2)
    assert np.isfinite(values).all()
    assert explainer.expected_value.shape == (2,)


def test_hgb_explainer_uses_minimum_evaluations_for_masker():
    class _ExplainerSpy:
        masker = SimpleNamespace(shape=(1, 56))
        max_evals = None

        def __call__(self, frame, *, max_evals):
            self.max_evals = max_evals
            return SimpleNamespace(values=np.zeros((len(frame), 56, 2)))

    categories = {}
    reference = pd.DataFrame({"amount": [0.0]})
    explainer = _HGBPermutationExplainer(
        SimpleNamespace(predict_proba=lambda frame: np.array([[0.7, 0.3]])),
        reference,
        ["amount"],
        categories,
    )
    spy = _ExplainerSpy()
    explainer._explainer = spy

    values = explainer.shap_values(reference)

    assert spy.max_evals == 113
    assert values.shape == (1, 56, 2)
