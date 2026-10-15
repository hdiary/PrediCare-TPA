"""Point d'entrée FastAPI de PrediCare TPA."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import db
from api.bootstrap import ensure_demo_users
from api.config import get_settings
from api.routers import admin, auth, health

logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger("predicare")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.jwt_secret.startswith("change_me") or len(settings.jwt_secret) < 32:
        logger.warning("JWT_SECRET faible ou par défaut : générer avec `openssl rand -hex 32`")
    db.init_pool()
    ensure_demo_users()
    yield
    db.close_pool()


app = FastAPI(
    title="PrediCare TPA API",
    version=health.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(db.DatabaseUnavailableError)
async def database_unavailable_handler(_: Request, exc: db.DatabaseUnavailableError):
    logger.error("database_unavailable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Base de données indisponible"})


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)
