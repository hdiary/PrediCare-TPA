"""Compatibility imports; the active model state lives only in ``ml_service``."""

from api.services.ml_service import (
    ModelRegistry,
    ModelUnavailableError,
    get_registry,
    registry,
)
from api.services.model_types import ModelBundle

__all__ = [
    "ModelBundle",
    "ModelRegistry",
    "ModelUnavailableError",
    "get_registry",
    "registry",
]
