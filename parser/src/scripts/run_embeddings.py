"""Generate embeddings for the parsed document via the ingestion pipeline."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from rag.ingestion import IngestionPipeline
from src.config import JSON_OUTPUT_FILE

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the ingestion pipeline with embeddings enabled."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=JSON_OUTPUT_FILE,
        help="Path to the parsed_document.json file.",
    )
    parser.add_argument(
        "--allow-embed-fallback",
        action="store_true",
        help="Allow deterministic fallback embeddings if OPENAI_API_KEY is not set.",
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=64,
        help="Batch size for embedding API calls (default: 64).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.source.exists():
        raise SystemExit(f"JSON file not found: {args.source}")

    pipeline = IngestionPipeline(
        enable_embeddings=True,
        allow_embedding_fallback=args.allow_embed_fallback,
        embedding_batch_size=args.embedding_batch_size,
    )
    document_id = pipeline.ingest(args.source)
    logging.info("Completed ingestion for document ID %s", document_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

