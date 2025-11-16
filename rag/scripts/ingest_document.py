"""CLI helper to ingest parsed documents into PostgreSQL."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from rag.ingestion import IngestionPipeline

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest a parsed building code JSON file.")
    parser.add_argument("source", type=Path, help="Path to the parsed_document.json file")
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip embedding generation (useful for offline/local testing).",
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pipeline = IngestionPipeline(
        enable_embeddings=not args.skip_embeddings,
        allow_embedding_fallback=args.allow_embed_fallback,
        embedding_batch_size=args.embedding_batch_size,
    )
    document_id = pipeline.ingest(args.source)
    print(f"Ingested document ID: {document_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
