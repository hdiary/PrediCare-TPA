"""Point d'entrée FastAPI de PrediCare TPA."""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine

from api import db
from api.bootstrap import ensure_demo_users, ensure_seed_users, ensure_user_identifiers
from api.config import get_settings
from api.routers import (
    admin, alerts, auth, bi, chat, factures, health, model, predict,
    ordonnances, rag_corpus,
)
from api.services.metrics import http_metrics
from api.logging_config import configure_logging
from api.middleware import BodySizeLimitMiddleware
from api.routers import invoices
from api.services.model_registry import ModelUnavailableError, registry
from api.validation import InvoiceRejected
from api.v1.router import router as api_v1_router

configure_logging()
logger = logging.getLogger("predicare")


def _initial_model_load() -> None:
    pool = db.get_pool()
    if pool is None:
        return
    try:
        with pool.connection(timeout=5) as conn:
            try:
                registry.initialize(conn)
            except (FileNotFoundError, ModelUnavailableError):
                registry.load_active(conn)
    except ModelUnavailableError as exc:
        logger.warning("modèle non chargé au démarrage (nouvelle tentative à la demande): %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.jwt_secret.startswith("change_me") or len(settings.jwt_secret) < 32:
        logger.warning("JWT_SECRET faible ou par défaut : générer avec `openssl rand -hex 32`")
    db.init_pool()
    ensure_demo_users()
    ensure_seed_users()
    ensure_user_identifiers()
    database_url = settings.database_url
    if database_url.startswith(("postgresql://", "postgres://")):
        database_url = database_url.replace(
            "postgres://", "postgresql+psycopg://", 1
        ).replace("postgresql://", "postgresql+psycopg://", 1)
    app.state.rag_ingestion_engine = create_engine(database_url)
    app.state.rag_agent = None
    try:
        from rag.factory import create_agent

        app.state.rag_agent = create_agent()
    except ValueError as exc:
        logger.warning("assistant RAG indisponible : %s", exc)
    # En arrière-plan : un MLflow lent ou absent ne doit pas retarder le démarrage de l'API
    threading.Thread(target=_initial_model_load, daemon=True).start()
    yield
    rag_agent = getattr(app.state, "rag_agent", None)
    if rag_agent is not None:
        rag_agent.retriever.engine.dispose()
    app.state.rag_ingestion_engine.dispose()
    db.close_pool()


app = FastAPI(title="PrediCare TPA API", version=health.VERSION, lifespan=lifespan)

app.add_middleware(
    BodySizeLimitMiddleware,
    max_bytes=get_settings().max_body_bytes,
    path_limits={
        "/rag-corpus": 21 * 1024 * 1024,
        "/api/v1/rag-corpus": 21 * 1024 * 1024,
    },
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


@app.exception_handler(InvoiceRejected)
async def invoice_rejected_handler(_: Request, exc: InvoiceRejected):
    """Facture refusée : liste des codes du contrat de données (section 9.1)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": "Facture rejetée", "codes": exc.codes, "erreurs": exc.erreurs},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    """Requête mal formée : 422 lisible, sans écho des valeurs reçues."""
    errors = [
        {
            "field": ".".join(str(p) for p in e["loc"] if p != "body"),
            "message": e["msg"],
            "type": e["type"],
        }
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "Requête invalide", "errors": errors})


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(chat.assistant_router)
app.include_router(predict.router)
app.include_router(factures.router)
app.include_router(ordonnances.router)
app.include_router(model.router)
app.include_router(alerts.router)
app.include_router(invoices.router)
app.include_router(admin.router)
app.include_router(bi.router)
app.include_router(rag_corpus.router)
app.include_router(api_v1_router)
