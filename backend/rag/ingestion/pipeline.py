"""Idempotent PDF-to-pgvector ingestion."""
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import text
from sqlalchemy.engine import Engine

from rag.embeddings import EmbeddingClient
from rag.ingestion.chunker import Page, chunk_pages
from rag.retriever import _vector_literal


@dataclass(frozen=True)
class IngestionResult:
    document_id: int
    chunk_count: int
    skipped: bool


def read_pdf(path: Path) -> list[Page]:
    reader = PdfReader(str(path))
    return [Page(number=index, text=page.extract_text() or "")
            for index, page in enumerate(reader.pages, start=1)]


def ingest_pdf(path: Path, contract_id: str | None, engine: Engine,
               embeddings: EmbeddingClient, force: bool = False,
               formula: str | None = None, global_scope: bool = False
               ) -> IngestionResult:
    if global_scope:
        if contract_id or formula:
            raise ValueError("Global documents cannot have a contract or formula")
        scope = "global"
    elif formula:
        if contract_id:
            raise ValueError("Formula documents cannot have a contract ID")
        if formula not in {"ESSENTIEL", "CONFORT", "PREMIUM"}:
            raise ValueError(f"Unsupported formula: {formula}")
        scope = "formula"
    else:
        if not contract_id:
            raise ValueError("A contract ID is required for contract documents")
        with engine.connect() as connection:
            contract = connection.execute(text(
                "SELECT formule FROM contrats WHERE contrat_id = :contract_id"),
                {"contract_id": contract_id}).mappings().first()
        if contract is None:
            raise ValueError(f"Unknown contract ID: {contract_id}")
        scope = "contract"
        formula = None

    pdf_bytes = path.read_bytes()
    digest = sha256(pdf_bytes).hexdigest()
    with engine.connect() as connection:
        existing = connection.execute(text("""
            SELECT id, contrat_id, formule, scope FROM rag_documents
            WHERE sha256 = :sha256
        """), {"sha256": digest}).mappings().first()
    if existing and (existing["contrat_id"], existing["formule"],
                     existing["scope"]) != (contract_id, formula, scope):
        raise ValueError(
            "This PDF hash is already registered to a different scope")
    if existing and not force:
        return IngestionResult(existing["id"], 0, True)

    pages = read_pdf(path)
    chunks = chunk_pages(
        pages, contract_id if scope == "contract" else None,
        formula=formula if scope == "formula" else None,
        global_scope=scope == "global")
    if not chunks:
        raise ValueError(f"No extractable text found in PDF: {path.name}")
    vectors: list[list[float]] = []
    for offset in range(0, len(chunks), 64):
        vectors.extend(embeddings.embed(
            [chunk.content for chunk in chunks[offset:offset + 64]]))

    with engine.begin() as connection:
        row = connection.execute(text("""
            INSERT INTO rag_documents
                (contrat_id, formule, scope, filename, sha256, version, n_pages)
            VALUES (:contract_id, :formula, :scope, :filename, :sha256, 1, :n_pages)
            ON CONFLICT (sha256) DO UPDATE SET
                filename = EXCLUDED.filename,
                formule = EXCLUDED.formule,
                scope = EXCLUDED.scope,
                version = rag_documents.version + 1,
                n_pages = EXCLUDED.n_pages,
                ingested_at = now()
            RETURNING id, contrat_id, formule, scope
        """), {
            "contract_id": contract_id,
            "formula": formula,
            "scope": scope,
            "filename": path.name,
            "sha256": digest,
            "n_pages": len(pages),
        }).mappings().one()
        if (row["contrat_id"], row["formule"], row["scope"]) != (
                contract_id, formula, scope):
            raise ValueError(
                "This PDF hash is already registered to a different scope")
        document_id = row["id"]
        if scope == "global":
            connection.execute(text("DELETE FROM rag_semantic_cache"))
        elif scope == "formula":
            connection.execute(text("""
                DELETE FROM rag_semantic_cache
                WHERE contrat_id IN (
                    SELECT contrat_id FROM contrats WHERE formule = :formula
                )
            """), {"formula": formula})
        else:
            connection.execute(text(
                "DELETE FROM rag_semantic_cache WHERE contrat_id = :contract_id"),
                {"contract_id": contract_id})
        connection.execute(text(
            "DELETE FROM rag_chunks WHERE document_id = :document_id"),
            {"document_id": document_id})
        for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
            connection.execute(text("""
                INSERT INTO rag_chunks
                    (document_id, contrat_id, formule, scope, chunk_index,
                     content, embedding, article, page_start, page_end,
                     token_count, metadata)
                VALUES
                    (:document_id, :contract_id, :formula, :scope,
                     :chunk_index, :content,
                     CAST(:embedding AS vector), :article, :page_start, :page_end,
                     :token_count, CAST(:metadata AS jsonb))
            """), {
                "document_id": document_id,
                "contract_id": contract_id,
                "formula": formula,
                "scope": scope,
                "chunk_index": index,
                "content": chunk.content,
                "embedding": _vector_literal(vector),
                "article": chunk.article,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "token_count": chunk.token_count,
                "metadata": json.dumps({}),
            })
    return IngestionResult(document_id, len(chunks), False)
