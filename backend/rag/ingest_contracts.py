"""Command-line entry point for contract PDF ingestion."""
import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine

from rag.config import RagSettings
from rag.embeddings import EmbeddingClient
from rag.ingestion.pipeline import ingest_pdf


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract-id", required=True)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not args.pdf.is_file():
        parser.error(f"PDF not found: {args.pdf}")

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
        os.environ.get("LLM_API_KEY", ""), settings.embedding_model,
        settings.embedding_dim, settings.embedding_api_url)
    result = ingest_pdf(
        args.pdf, args.contract_id, engine, embedder, force=args.force)
    action = "skipped (already ingested)" if result.skipped else "ingested"
    print(f"{action}: document_id={result.document_id}, "
          f"chunks={result.chunk_count}")


if __name__ == "__main__":
    main()
