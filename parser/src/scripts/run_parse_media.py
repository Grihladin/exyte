"""Run the parsing pipeline to extract structure, tables, and figures."""

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
    JSON_OUTPUT_FILE,
)
from src.utils.table_markdown import rebuild_table_markdown

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run structure parsing and refresh table Markdown."
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
    parser.add_argument(
        "--skip-table-markdown",
        action="store_true",
        help="Skip rebuilding Markdown tables after parsing.",
    )
    parser.add_argument(
        "--table-markdown-overwrite",
        action="store_true",
        help="Rebuild Markdown for all tables (default: only missing).",
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
    )

    if not args.skip_table_markdown:
        logging.info("Rebuilding Markdown tables from %s", pdf_path)
        try:
            processed = rebuild_table_markdown(
                pdf_path=pdf_path,
                json_path=JSON_OUTPUT_FILE,
                overwrite=args.table_markdown_overwrite,
            )
        except FileNotFoundError as exc:
            logging.error("Failed to rebuild table Markdown: %s", exc)
            return 1
        if processed:
            logging.info("Updated Markdown for %d table(s).", processed)
        else:
            logging.info("Table Markdown already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
