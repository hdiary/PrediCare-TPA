"""Endpoint de santé, utilisé par le healthcheck Docker et l'écran d'administration."""
import time

import psycopg
from fastapi import APIRouter, Response

from api.db import get_pool
from api.schemas import HealthResponse

router = APIRouter(tags=["health"])

VERSION = "0.1.0"
_STARTED = time.monotonic()


def _check_database() -> str:
    pool = get_pool()
    if pool is None:
        return "pool_not_initialized"
    try:
        with pool.connection(timeout=3) as conn:
            conn.execute("SELECT 1")
        return "ok"
    except (psycopg.Error, Exception) as exc:  # noqa: BLE001
        return f"error: {type(exc).__name__}"


@router.get("/health", response_model=HealthResponse)
def health(response: Response):
    checks = {"database": _check_database()}
    # À compléter plus tard : checks["model"], checks["mlflow"], checks["migrations"]
    ok = all(v == "ok" for v in checks.values())
    if not ok:
        response.status_code = 503  # le healthcheck Docker passera en "unhealthy"
    return HealthResponse(
        status="ok" if ok else "degraded",
        version=VERSION,
        uptime_s=int(time.monotonic() - _STARTED),
        checks=checks,
    )
