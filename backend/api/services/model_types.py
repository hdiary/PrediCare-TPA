import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class ModelUnavailableError(Exception):
    """The active model could not be loaded and validated."""


@dataclass(frozen=True)
class ModelBundle:
    name: str
    version: str
    model: Any
    explainer: Any
    feature_names: list[str]
    loaded_at: datetime
    sha256: str = ""
    metrics: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    calibrator: Any = None


def decision_threshold(bundle: ModelBundle) -> float | None:
    """Seuil de décision enregistré avec le modèle (metadata.decision_threshold), si exploitable.

    Les scores des modèles boostés avec poids de classes ne sont pas des probabilités calibrées :
    le seuil n'a de sens que sur l'échelle du modèle qui l'a produit (ex. 0,9678 pour HGB,
    0,9999 pour LightGBM), d'où l'intérêt de le lire avec le modèle plutôt que dans le .env.
    """
    try:
        value = float((bundle.metadata or {}).get("decision_threshold"))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and 0.0 < value <= 1.0 else None
