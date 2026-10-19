"""Ingest all PDFs in corpus_rag using their contract/formula/global scope."""
import os
from pathlib import Path
import re

from sqlalchemy import create_engine

from rag.config import RagSettings
from rag.embeddings import EmbeddingClient
from rag.ingestion.pipeline import IngestionResult, ingest_pdf


_CONTRACT_PATTERN = re.compile(r"^CP_(CTR-\d{6})\.pdf$", re.IGNORECASE)
_FORMULA_PATTERN = re.compile(
    r"^Conditions_Generales_(ESSENTIEL|CONFORT|PREMIUM)\.pdf$",
    re.IGNORECASE,
)


def _scope(path: Path) -> tuple[str | None, str | None, bool]:
    contract_match = _CONTRACT_PATTERN.fullmatch(path.name)
    if contract_match and path.parent.name.casefold() == "conditions_particulieres":
        return contract_match.group(1).upper(), None, False

    formula_match = _FORMULA_PATTERN.fullmatch(path.name)
    if formula_match:
        return None, formula_match.group(1).upper(), False

    return None, None, True


def main() -> None:
    corpus = Path(os.environ.get("RAG_CORPUS_DIR", "/corpus_rag"))
    if not corpus.is_dir():
        raise FileNotFoundError(f"RAG corpus directory does not exist: {corpus}")
    pdfs = sorted(path for path in corpus.rglob("*") if path.is_file()
                  and path.suffix.casefold() == ".pdf")
    if not pdfs:
        raise FileNotFoundError(f"No PDF files found in RAG corpus: {corpus}")

    settings = RagSettings.from_env()
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql+psycopg://", 1)
    engine = create_engine(database_url)
    embedder = EmbeddingClient(
        settings.llm_api_key, settings.embedding_model,
        settings.embedding_dim, settings.embedding_api_url)

    ingested = 0
    skipped = 0
    chunks = 0
    for pdf in pdfs:
        contract_id, formula, global_scope = _scope(pdf)
        result: IngestionResult = ingest_pdf(
            pdf, contract_id, engine, embedder,
            formula=formula, global_scope=global_scope)
        if result.skipped:
            skipped += 1
            print(f"unchanged: {pdf.relative_to(corpus)}")
        else:
            ingested += 1
            chunks += result.chunk_count
            scope = (f"contract {contract_id}" if contract_id else
                     f"formula {formula}" if formula else "global")
            print(f"ingested: {pdf.relative_to(corpus)} "
                  f"({scope}, {result.chunk_count} chunks)")

    print(f"Corpus ready: {ingested} ingested, {skipped} unchanged, "
          f"{chunks} chunks.")


if __name__ == "__main__":
    main()
