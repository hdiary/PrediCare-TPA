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
