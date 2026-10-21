"""Manager-only document management for the RAG corpus."""
import logging
import os
from pathlib import Path
import re

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pypdf.errors import PdfReadError
from sqlalchemy.exc import SQLAlchemyError

from api.db import get_db
from api.deps import require_role
from rag.ingest_corpus import _scope
from rag.ingestion.pipeline import IngestionResult, ingest_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag-corpus", tags=["rag-corpus"])
manager_only = Depends(require_role("gestionnaire", "administrateur"))
MAX_PDF_SIZE = 20 * 1024 * 1024
_CONTRACT_FILENAME = re.compile(r"^CP_(CTR-\d{6})\.pdf$", re.IGNORECASE)


@router.get("", dependencies=[manager_only])
def list_corpus_documents(conn=Depends(get_db)):
    rows = conn.execute(
        "SELECT d.id, d.filename, d.scope, d.contrat_id, d.formule, d.n_pages, "
        "d.ingested_at, count(c.id) AS chunks "
        "FROM rag_documents d LEFT JOIN rag_chunks c ON c.document_id = d.id "
        "GROUP BY d.id ORDER BY d.ingested_at DESC, d.id DESC LIMIT 200"
    ).fetchall()
    return {"items": [dict(row) for row in rows]}


@router.post("", status_code=201)
def add_corpus_document(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_role("gestionnaire", "administrateur")),
    conn=Depends(get_db),
):
    del conn, user
    filename = file.filename or ""
    if (
        not filename
        or "/" in filename
        or "\\" in filename
        or filename.startswith(".")
        or Path(filename).suffix.casefold() != ".pdf"
    ):
        raise HTTPException(status_code=422, detail="Nom de fichier PDF invalide")

    content = file.file.read(MAX_PDF_SIZE + 1)
    if len(content) > MAX_PDF_SIZE:
        raise HTTPException(status_code=413, detail="Le PDF ne doit pas dépasser 20 Mo")
    if b"%PDF-" not in content[:1024]:
        raise HTTPException(status_code=422, detail="Le fichier envoyé n'est pas un PDF valide")

    agent = getattr(request.app.state, "rag_agent", None)
    engine = getattr(request.app.state, "rag_ingestion_engine", None)
    if agent is None or engine is None:
        raise HTTPException(
            status_code=503,
            detail="L'indexation RAG est indisponible. Vérifiez la configuration des embeddings.",
        )

    corpus = Path(os.environ.get("RAG_CORPUS_DIR", "/manager-rag-corpus"))
    contract_match = _CONTRACT_FILENAME.fullmatch(filename)
    directory = corpus / "conditions_particulieres" if contract_match else corpus
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / filename
    if destination.exists():
        raise HTTPException(status_code=409, detail="Un document porte déjà ce nom")
    destination.write_bytes(content)

    indexed = False
    try:
        contract_id, formula, global_scope = _scope(destination)
        result: IngestionResult = ingest_pdf(
            destination,
            contract_id,
            engine,
            agent.embeddings,
            formula=formula,
            global_scope=global_scope,
        )
        indexed = True
    except PdfReadError as exc:
        raise HTTPException(status_code=422, detail="Impossible de lire ce PDF") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("rag_corpus_ingestion_failed", extra={"filename": filename})
        raise HTTPException(
            status_code=502,
            detail="Le service d'embeddings n'a pas pu indexer le document.",
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("rag_corpus_database_failed", extra={"filename": filename})
        raise HTTPException(
            status_code=503,
            detail="La base de données RAG ne peut pas indexer le document.",
        ) from exc
    finally:
        if not indexed:
            destination.unlink(missing_ok=True)

    return {
        "id": result.document_id,
        "filename": filename,
        "scope": "contract" if contract_id else "formula" if formula else "global",
        "contract_id": contract_id,
        "formula": formula,
        "chunks": result.chunk_count,
        "already_indexed": result.skipped,
    }
