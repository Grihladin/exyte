"""Run the parsing pipeline to extract structure, tables, and figures (no OCR)."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from src import pipeline
from src.config import (
    DEFAULT_PAGE_COUNT,
    DEFAULT_PDF_PATH,
    DEFAULT_START_PAGE_INDEX,
)

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run structure parsing and save table/figure images."
    )
    parser.add_argument(
        "pdf",
        nargs="?",
        type=Path,
        default=DEFAULT_PDF_PATH,
        help="Path to the PDF file (defaults to configured building code).",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=DEFAULT_PAGE_COUNT,
        help="Number of pages to parse (default: entire configured range).",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=DEFAULT_START_PAGE_INDEX + 1,
        dest="start_page",
        help="1-indexed page number to start parsing from.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.pages <= 0:
        raise SystemExit("--pages must be positive")
    if args.start_page <= 0:
        raise SystemExit("--start must be >= 1")

    pdf_path = args.pdf
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    pipeline.run_structure_phase(
        pdf_path=pdf_path,
        num_pages=args.pages,
        start_page=args.start_page - 1,
        enable_table_ocr=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

