"""Versioned aliases for the existing non-RAG API."""
from fastapi import APIRouter

from api.routers import admin, alerts, auth, bi, chat, factures, model, predict, rag_corpus

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(predict.router)
router.include_router(factures.router)
router.include_router(model.router)
router.include_router(alerts.router)
router.include_router(admin.router)
router.include_router(bi.router)
router.include_router(rag_corpus.router)
router.include_router(chat.assistant_router)
