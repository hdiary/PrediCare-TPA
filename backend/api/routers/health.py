"""Endpoint de santé, utilisé par le healthcheck Docker et l'écran d'administration."""
import time

import httpx
from fastapi import APIRouter, Response

from api.config import get_settings
from api.db import get_pool
from api.schemas import HealthResponse
from api.services.model_registry import registry

router = APIRouter(tags=["health"])

VERSION = "0.2.0"
_STARTED = time.monotonic()


def _check_database() -> str:
    pool = get_pool()
    if pool is None:
        return "pool_not_initialized"
    try:
        with pool.connection(timeout=3) as conn:
            conn.execute("SELECT 1")
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"error: {type(exc).__name__}"


def _check_n8n() -> str:
    health_url = get_settings().n8n_health_url
    if not health_url:
        return "not_configured"
    try:
        response = httpx.get(health_url, timeout=2)
        return "ok" if response.is_success else "unavailable"
    except httpx.HTTPError:
        return "unavailable"


@router.get("/health", response_model=HealthResponse)
def health(response: Response):
    bundle = registry.get()
    checks = {
        "database": _check_database(),
        "model": "ok" if bundle else "not_loaded",
        "n8n": _check_n8n(),
    }
    # Seule la base est critique (503) : sans modèle l'API reste utilisable (login, alertes...)
    if checks["database"] != "ok":
        response.status_code = 503
    return HealthResponse(
        status="ok" if all(v == "ok" for v in checks.values()) else "degraded",
        version=VERSION,
        uptime_s=int(time.monotonic() - _STARTED),
        checks=checks,
        model_version=bundle.version if bundle else None,
    )
