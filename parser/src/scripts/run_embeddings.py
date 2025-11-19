"""Generate embeddings for the parsed document via the ingestion pipeline."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

SCRIPT_PATH = Path(__file__).resolve()
PARSER_ROOT = SCRIPT_PATH.parents[2]  # .../parser
REPO_ROOT = SCRIPT_PATH.parents[3]  # .../parsing

for path in (PARSER_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from rag.ingestion import IngestionPipeline  # noqa: E402 (depends on sys.path tweak)
from src.config import JSON_OUTPUT_FILE  # noqa: E402 (depends on sys.path tweak)

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
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.source.exists():
        raise SystemExit(f"JSON file not found: {args.source}")

    pipeline = IngestionPipeline(
        enable_embeddings=not args.skip_embeddings,
        allow_embedding_fallback=args.allow_embed_fallback,
        embedding_batch_size=args.embedding_batch_size,
    )
    document_id = pipeline.ingest(args.source)
    logging.info("Completed ingestion for document ID %s", document_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
