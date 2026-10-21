"""Database-backed model registry and safe model activation."""
import hashlib
import json
import logging
import shutil
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from psycopg.types.json import Jsonb

from api.config import get_settings
from api.services.model_types import ModelBundle, ModelUnavailableError

logger = logging.getLogger(__name__)
_SEED_DIRECTORY = Path(__file__).resolve().parents[2] / "ml" / "models_seed"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelUnavailableError(f"Impossible de lire {path.name}: {exc}") from exc


class _HGBPermutationExplainer:
    def __init__(self, model, reference, features: list[str], categories: dict):
        import numpy as np
        import pandas as pd
        import shap

        self.features = features
        self.categories = categories
        encoded_reference = self._encode(reference, pd)
        self.expected_value = np.asarray(model.predict_proba(reference)[0])
        self._explainer = shap.PermutationExplainer(
            self._predict_proba(model, pd), encoded_reference,
            feature_names=features,
        )

    def _encode(self, frame, pandas):
        encoded = frame.copy()
        for name, levels in self.categories.items():
            encoded[name] = pandas.Categorical(
                frame[name], categories=levels
            ).codes.astype(float)
        encoded = encoded.apply(pandas.to_numeric, errors="raise")
        return encoded.to_numpy(dtype="float64")

    def _predict_proba(self, model, pandas):
        import numpy as np

        def predict(values):
            frame = pandas.DataFrame(values, columns=self.features)
            for name, levels in self.categories.items():
                codes = np.rint(
                    pandas.to_numeric(frame[name], errors="coerce")
                ).astype("Int64")
                frame[name] = pandas.Categorical(
                    [
                        levels[int(code)]
                        if not pandas.isna(code) and 0 <= int(code) < len(levels)
                        else None
                        for code in codes
                    ],
                    categories=levels,
                )
            return model.predict_proba(frame)

        return predict

    def shap_values(self, frame):
        import pandas as pd

        encoded = self._encode(frame, pd)
        min_evals = 2 * self._explainer.masker.shape[1] + 1
        return self._explainer(encoded, max_evals=min_evals).values


class ModelRegistry:
    def __init__(self) -> None:
        self._bundle: ModelBundle | None = None
        self._lock = threading.RLock()
        self._last_attempt: float | None = None
        self.last_error: str | None = None

    def get(self) -> ModelBundle | None:
        return self._bundle

    def _store(self) -> Path:
        return Path(get_settings().model_store_path)

    def initialize(self, conn) -> ModelBundle | None:
        """Synchronize seed artifacts and import model versions not yet registered."""
        store = self._store()
        store.mkdir(parents=True, exist_ok=True)
        if not _SEED_DIRECTORY.is_dir():
            raise ModelUnavailableError(f"Répertoire de modèles seed absent: {_SEED_DIRECTORY}")

        for seed_dir in sorted(_SEED_DIRECTORY.glob("v*")):
            if not seed_dir.is_dir():
                continue
            store_dir = store / seed_dir.name
            if not store_dir.exists():
                shutil.copytree(seed_dir, store_dir)

        imported = False
        for metadata_path in sorted(store.glob("v*/metadata.json")):
            metadata = _read_json(metadata_path)
            exists = conn.execute(
                "SELECT 1 FROM model_versions WHERE version = %s",
                (metadata["version"],),
            ).fetchone()
            if exists:
                continue

            active = conn.execute(
                "SELECT 1 FROM model_versions WHERE status = 'ACTIF' LIMIT 1"
            ).fetchone()
            status = (
                "ACTIF"
                if metadata.get("status") == "ACTIF" and active is None
                else "ARCHIVE"
            )
            model_path = metadata_path.parent / metadata["artifact"]
            conn.execute(
                "INSERT INTO model_versions "
                "(version, artifact_path, sha256, metrics, status, metadata, trained_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    metadata["version"],
                    str(model_path.resolve()),
                    metadata["sha256"],
                    Jsonb(metadata["metrics"]),
                    status,
                    Jsonb(metadata),
                    metadata.get("trained_at"),
                ),
            )
            imported = True
        if imported:
            conn.commit()
        return self.load_active(conn, force=True)

    def _load_record(self, record: dict) -> ModelBundle:
        path = Path(record["artifact_path"])
        if not path.is_file():
            raise ModelUnavailableError(f"Fichier du modèle absent: {path}")
        actual_hash = _sha256(path)
        expected_hash = str(record["sha256"]).strip()
        if actual_hash != expected_hash:
            raise ModelUnavailableError(f"SHA-256 invalide pour la version {record['version']}")

        schema = _read_json(path.parent / "feature_schema.json")
        sample = _read_json(path.parent / "reference_sample.json")
        try:
            import joblib
            import numpy as np
            import pandas as pd
            import shap

            artifact = joblib.load(path)
            model = artifact.get("model", artifact)
            features = schema["features"]
            categories = schema.get("categories", {})
            rows = sample["rows"]
            if not features or not rows or any(set(row) != set(features) for row in rows):
                raise ValueError("Le schéma ou l'échantillon de référence est incomplet")
            reference = pd.DataFrame(rows, columns=features)
            for name, values in categories.items():
                reference[name] = pd.Categorical(reference[name], categories=values)
            probabilities = np.asarray(model.predict_proba(reference), dtype=float)
            if probabilities.ndim != 2 or probabilities.shape[0] != len(reference):
                raise ValueError("Le modèle a retourné un score de forme invalide")
            positive_scores = probabilities[:, -1]
            if not np.isfinite(positive_scores).all() or (
                (positive_scores < 0) | (positive_scores > 1)
            ).any():
                raise ValueError("Le modèle a retourné un score hors de [0, 1]")
            if isinstance(artifact, dict) and artifact.get("algo") == "hgb":
                explainer = _HGBPermutationExplainer(
                    model, reference, features, categories
                )
            else:
                explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(reference)
            if shap_values is None or not np.isfinite(np.asarray(shap_values)).all():
                raise ValueError("Le test de fumée SHAP a échoué")
        except ModelUnavailableError:
            raise
        except Exception as exc:
            raise ModelUnavailableError(
                f"Test de fumée échoué pour la version {record['version']}: {exc}"
            ) from exc

        metadata = record.get("metadata") or {}
        metrics = record.get("metrics") or {}
        return ModelBundle(
            name=metadata.get("model_name", "predicare-fraud"),
            version=record["version"],
            model=model,
            explainer=explainer,
            feature_names=features,
            loaded_at=datetime.now(UTC),
            sha256=actual_hash,
            metrics=metrics,
            metadata=metadata,
        )

    def load_active(self, conn, force: bool = False) -> ModelBundle | None:
        record = conn.execute(
            "SELECT version, artifact_path, sha256, metrics, metadata "
            "FROM model_versions WHERE status = 'ACTIF'"
        ).fetchone()
        if record is None:
            self.last_error = "Aucune version de modèle active n'est enregistrée"
            return None
        with self._lock:
            current = self._bundle
            if current and current.version == record["version"] and not force:
                return current
            self._last_attempt = time.monotonic()
            try:
                bundle = self._load_record(record)
            except ModelUnavailableError as exc:
                self.last_error = str(exc)
                logger.error("model_load_failed version=%s error=%s", record["version"], exc)
                if current is not None:
                    return current
                raise
            self._bundle = bundle
            self.last_error = None
            logger.info("model_loaded version=%s sha256=%s", bundle.version, bundle.sha256)
            return bundle

    def ensure_loaded(self, conn=None):
        """Reload the active database version when another API worker changes it."""
        if conn is not None:
            return self.load_active(conn)
        from api import db

        pool = db.get_pool()
        if pool is None:
            return self._bundle
        with pool.connection(timeout=5) as pool_conn:
            return self.load_active(pool_conn)

    def list_versions(self, conn) -> list[dict]:
        rows = conn.execute(
            "SELECT version, status, metrics, metadata, trained_at, activated_at, sha256 "
            "FROM model_versions ORDER BY trained_at DESC NULLS LAST, version DESC"
        ).fetchall()
        return [
            {
                "version": row["version"],
                "status": row["status"],
                "created_at": row["trained_at"].isoformat() if row["trained_at"] else None,
                "activated_at": row["activated_at"].isoformat() if row["activated_at"] else None,
                "recall": (row["metrics"] or {}).get("test", {}).get("recall"),
                "precision": (row["metrics"] or {}).get("test", {}).get("precision"),
                "sha256": row["sha256"],
                "metadata": row["metadata"] or {},
            }
            for row in rows
        ]

    def activate_version(self, conn, version: str, user: dict) -> ModelBundle:
        """Validate candidate bytes before atomically changing the active DB row."""
        with self._lock:
            record = conn.execute(
                "SELECT version, artifact_path, sha256, metrics, metadata "
                "FROM model_versions WHERE version = %s",
                (version,),
            ).fetchone()
            if record is None:
                raise ModelUnavailableError(f"Version de modèle inconnue: {version}")
            candidate = self._load_record(record)
            previous_row = conn.execute(
                "SELECT version FROM model_versions WHERE status = 'ACTIF'"
            ).fetchone()
            previous = previous_row["version"] if previous_row else None
            try:
                with conn.transaction():
                    conn.execute(
                        "UPDATE model_versions SET status = CASE WHEN version = %s "
                        "THEN 'ACTIF' ELSE 'ARCHIVE' END, "
                        "active_par = CASE WHEN version = %s THEN %s ELSE active_par END, "
                        "activated_at = CASE WHEN version = %s THEN now() ELSE activated_at END",
                        (version, version, user["user_id"], version),
                    )
                    conn.execute(
                        "INSERT INTO journal_audit "
                        "(type_evenement, utilisateur_id, type_entite, entite_id, "
                        "entree, sortie) VALUES (%s, %s, %s, %s, %s, %s)",
                        (
                            "modele_charge",
                            user["user_id"],
                            "model",
                            version,
                            Jsonb({"previous_version": previous, "action": "activate"}),
                            Jsonb({"active_version": version}),
                        ),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            self._bundle = candidate
            self.last_error = None
            logger.info(
                "model_activated actor=%s previous=%s version=%s",
                user["user_id"],
                previous,
                version,
            )
            return candidate

    def metrics(self, conn) -> dict:
        row = conn.execute(
            "SELECT version, metrics, metadata FROM model_versions WHERE status = 'ACTIF'"
        ).fetchone()
        if row is None:
            raise ModelUnavailableError("Aucune version de modèle active")
        return {
            "version": row["version"],
            "metrics": row["metrics"] or {},
            "metadata": row["metadata"] or {},
        }

    def current(self, conn) -> dict:
        bundle = self.ensure_loaded(conn)
        if bundle is None:
            raise ModelUnavailableError(self.last_error or "Modèle indisponible")
        return {
            "version": bundle.version,
            "loaded_at": bundle.loaded_at.isoformat(),
            "sha256": bundle.sha256,
            "feature_count": len(bundle.feature_names),
            "last_error": self.last_error,
            "metadata": bundle.metadata,
        }


registry = ModelRegistry()


def get_registry() -> ModelRegistry:
    return registry
