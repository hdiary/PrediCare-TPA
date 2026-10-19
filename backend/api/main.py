"""Point d'entrée FastAPI de PrediCare TPA."""
import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import db
from api.bootstrap import ensure_demo_users
from api.config import get_settings
from api.routers import admin, alerts, auth, chat, factures, health, kpis, model, predict
from api.services.metrics import http_metrics
from api.services.model_registry import ModelUnavailableError, registry
from api.validation import InvoiceRejected
from api.v1.router import router as api_v1_router

logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
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
    try:
        from rag.factory import create_agent

        app.state.rag_agent = create_agent()
    except ValueError as exc:
        app.state.rag_agent = None
        logger.warning("rag_disabled: %s", exc)
    # En arrière-plan : un MLflow lent ou absent ne doit pas retarder le démarrage de l'API
    threading.Thread(target=_initial_model_load, daemon=True).start()
    yield
    rag_agent = getattr(app.state, "rag_agent", None)
    if rag_agent is not None:
        rag_agent.retriever.engine.dispose()
    db.close_pool()


app = FastAPI(title="PrediCare TPA API", version=health.VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # En-têtes lisibles par le front (sans cela, le navigateur les masque en cross-origin)
    expose_headers=["X-Total-Count", "X-Request-ID", "Retry-After"],
)


@app.middleware("http")
async def observability(request: Request, call_next):
    """Identifiant de requête (X-Request-ID) + métriques de volume, erreurs et latence (P3-18)."""
    request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request.state.request_id
        return response
    finally:
        route = request.scope.get("route")
        http_metrics.record(
            request.method,
            getattr(route, "path", "non_routee"),
            status_code,
            (time.perf_counter() - started) * 1000,
        )


@app.exception_handler(db.DatabaseUnavailableError)
async def database_unavailable_handler(_: Request, exc: db.DatabaseUnavailableError):
    logger.error("database_unavailable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Base de données indisponible"})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    """Erreur inattendue : message neutre pour le front, détail dans les logs (avec l'id de requête)."""
    request_id = getattr(request.state, "request_id", None)
    logger.error("unhandled_error request_id=%s error=%r", request_id, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erreur interne du serveur", "request_id": request_id},
    )


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
app.include_router(predict.router)
app.include_router(factures.router)
app.include_router(model.router)
app.include_router(alerts.router)
app.include_router(kpis.router)
app.include_router(admin.router)
app.include_router(api_v1_router)
