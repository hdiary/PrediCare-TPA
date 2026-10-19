"""Chargement du modèle actif depuis MLflow (alias de version) avec échange atomique.

Contrat avec le rôle A (voir README du backend) :
  - le modèle est enregistré dans MLflow sous le nom MLFLOW_MODEL_NAME ;
  - la version active porte l'alias MLFLOW_MODEL_ALIAS (par défaut « champion ») ;
  - le modèle est loggé avec l'API sklearn (XGBClassifier / LGBMClassifier), entraîné sur
    un DataFrame pour que les noms de colonnes soient conservés.
Retour arrière = déplacer l'alias sur l'ancienne version, puis POST /admin/model/reload.
"""
import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from api.config import get_settings

logger = logging.getLogger(__name__)


class ModelUnavailableError(Exception):
    """Le modèle actif n'a pas pu être chargé."""


@dataclass(frozen=True)
class ModelBundle:
    name: str
    version: str
    model: Any
    explainer: Any
    feature_names: list[str]
    loaded_at: datetime


def _feature_names(model) -> list[str]:
    names = getattr(model, "feature_names_in_", None)
    if names is not None:
        return [str(n) for n in names]
    if hasattr(model, "get_booster"):
        booster_names = model.get_booster().feature_names
        if booster_names:
            return list(booster_names)
    if getattr(model, "feature_name_", None):
        return list(model.feature_name_)
    raise ModelUnavailableError(
        "Noms de colonnes introuvables : entraîner le modèle sur un DataFrame pandas"
    )


def _load_native(uri: str):
    import mlflow.sklearn
    import mlflow.xgboost

    try:
        return mlflow.xgboost.load_model(uri)
    except Exception as xgb_err:  # noqa: BLE001
        try:
            return mlflow.sklearn.load_model(uri)
        except Exception as sk_err:  # noqa: BLE001
            raise ModelUnavailableError(
                f"chargement impossible (xgboost: {xgb_err}; sklearn: {sk_err})"
            ) from sk_err


class ModelRegistry:
    def __init__(self) -> None:
        self._bundle: ModelBundle | None = None
        self._lock = threading.Lock()
        self._last_attempt: float | None = None
        self.last_error: str | None = None

    def get(self) -> ModelBundle | None:
        return self._bundle

    def load_active(self, force: bool = False) -> ModelBundle:
        """Charge la version portant l'alias actif. Échange la référence en une affectation."""
        settings = get_settings()
        name, alias = settings.mlflow_model_name, settings.mlflow_model_alias
        with self._lock:
            self._last_attempt = time.monotonic()
            try:
                import mlflow
                import shap

                mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
                mv = mlflow.MlflowClient().get_model_version_by_alias(name, alias)
                version = str(mv.version)
                current = self._bundle
                if current and current.version == version and not force:
                    return current
                model = _load_native(f"models:/{name}/{version}")
                bundle = ModelBundle(
                    name=name,
                    version=version,
                    model=model,
                    explainer=shap.TreeExplainer(model),  # créé une seule fois
                    feature_names=_feature_names(model),
                    loaded_at=datetime.now(UTC),
                )
            except ModelUnavailableError as exc:
                self.last_error = str(exc)
                raise
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                raise ModelUnavailableError(str(exc)) from exc
            self._bundle = bundle  # échange atomique : les requêtes en cours gardent l'ancien
            self.last_error = None
            logger.info("model_loaded name=%s version=%s", name, version)
            return bundle

    def ensure_loaded(self) -> ModelBundle | None:
        """Retourne le modèle, en retentant le chargement (au plus toutes les N secondes)."""
        if self._bundle is not None:
            return self._bundle
        interval = get_settings().model_retry_interval_s
        if self._last_attempt is not None and time.monotonic() - self._last_attempt < interval:
            return None
        try:
            return self.load_active()
        except ModelUnavailableError as exc:
            logger.warning("model_load_failed: %s", exc)
            return None


registry = ModelRegistry()


def get_registry() -> ModelRegistry:
    """Dépendance FastAPI (surchargeable dans les tests)."""
    return registry
