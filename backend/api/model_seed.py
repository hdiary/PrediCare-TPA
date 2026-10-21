"""Build versioned seed directories from the repository's legacy model registry."""
import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "ml" / "models"
SEED = ROOT / "ml" / "models_seed"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_artifact(path: Path) -> dict:
    import joblib

    artifact = joblib.load(path)
    if not isinstance(artifact, dict) or not artifact.get("features"):
        raise ValueError(f"Artefact invalide ou sans clé features: {path}")
    return artifact


def _write_derived_files(version_dir: Path, artifact: dict) -> list[str]:
    """Derive schema and reference data exclusively from the loaded artifact."""
    features = list(artifact["features"])
    categories = {name: list(values) for name, values in artifact.get("categories", {}).items()}
    schema_path = version_dir / "feature_schema.json"
    current_schema = json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.exists() else {}
    if current_schema.get("features") != features or current_schema.get("categories", {}) != categories:
        schema_path.write_text(
            json.dumps({"features": features, "categories": categories}, indent=2),
            encoding="utf-8",
        )
    row = {
        name: (categories[name][0] if name in categories and categories[name] else 0.0)
        for name in features
    }
    (version_dir / "reference_sample.json").write_text(
        json.dumps({"rows": [row]}, indent=2), encoding="utf-8"
    )
    return features


def check_seed_coherence() -> None:
    """Fail if a seed schema differs from its loaded joblib feature order."""
    mismatches = []
    for metadata_path in sorted(SEED.glob("v*/metadata.json")):
        version_dir = metadata_path.parent
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        artifact = _load_artifact(version_dir / metadata["artifact"])
        expected = list(artifact["features"])
        schema = json.loads((version_dir / "feature_schema.json").read_text(encoding="utf-8"))
        if schema.get("features") != expected:
            mismatches.append(version_dir.name)
    if mismatches:
        raise ValueError("feature_schema.json incohérent avec le joblib: " + ", ".join(mismatches))


def _synchronize_existing_seed() -> None:
    for metadata_path in sorted(SEED.glob("v*/metadata.json")):
        version_dir = metadata_path.parent
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        _write_derived_files(version_dir, _load_artifact(version_dir / metadata["artifact"]))


def _candidate_versions(registry: dict) -> list[dict]:
    versions = registry["versions"]
    active = next(item for item in versions if item["version"] == registry["active"])
    hgb = next((item for item in versions if item.get("algo") == "hgb"), None)
    candidates = [active]
    if hgb and hgb["version"] != active["version"]:
        candidates.append(hgb)
    for item in sorted(
        versions, key=lambda item: item.get("trained_at", ""), reverse=True
    ):
        if len(candidates) == 2:
            break
        if item["version"] not in {candidate["version"] for candidate in candidates}:
            candidates.append(item)
    return candidates


def prepare_seed() -> None:
    SEED.mkdir(parents=True, exist_ok=True)
    registry = json.loads((LEGACY / "registry.json").read_text(encoding="utf-8"))
    candidates = _candidate_versions(registry)
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"

    for item in candidates:
        version_dir = SEED / f"v{item['version']}"
        metadata_path = version_dir / "metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            artifact = _load_artifact(version_dir / metadata["artifact"])
            _write_derived_files(version_dir, artifact)
            continue

        artifact_source = LEGACY / item["file"]
        artifact = _load_artifact(artifact_source)
        version_dir.mkdir(parents=True, exist_ok=True)
        artifact_name = artifact_source.name
        shutil.copy2(artifact_source, version_dir / artifact_name)
        features = _write_derived_files(version_dir, artifact)
        metadata = {
            "version": item["version"],
            "artifact": artifact_name,
            "sha256": _sha256(version_dir / artifact_name),
            "status": "ACTIF" if item["version"] == registry["active"] else "ARCHIVE",
            "model_name": "predicare-fraud",
            "commit": commit,
            "trained_at": item.get("trained_at") or datetime.now().isoformat(),
            "metrics": {"test": item.get("test", {}), "valid": item.get("valid", {})},
            "decision_threshold": artifact.get("seuil"),
            "algorithm": artifact.get("algo"),
            "parameters": artifact.get("params", {}),
            "features": features,
        }
        metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    _synchronize_existing_seed()


if __name__ == "__main__":
    prepare_seed()
    check_seed_coherence()
