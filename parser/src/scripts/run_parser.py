"""Run the configured building-code parsing pipeline."""

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

from src import pipeline  # noqa: E402
from src.config import (  # noqa: E402
    DEFAULT_PAGE_COUNT,
    DEFAULT_PDF_PATH,
    DEFAULT_START_PAGE_INDEX,
    JSON_OUTPUT_FILE,
)
from src.utils.table_markdown import rebuild_table_markdown  # noqa: E402

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse the configured building code PDF starting at page 32."
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=DEFAULT_PDF_PATH,
        help="Path to the source PDF (defaults to 2021 International Building Code).",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=DEFAULT_PAGE_COUNT,
        help="Number of pages to parse (defaults to the configured full range).",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=DEFAULT_START_PAGE_INDEX + 1,
        help="1-indexed page number to begin parsing from (default: 32).",
    )
    parser.add_argument(
        "--skip-table-refresh",
        action="store_true",
        help="Skip rebuilding Markdown for detected tables.",
    )
    parser.add_argument(
        "--overwrite-table-markdown",
        action="store_true",
        help="Force Markdown regeneration even if an entry already exists.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.pages <= 0:
        raise SystemExit("--pages must be positive")
    if args.start_page <= 0:
        raise SystemExit("--start-page must be >= 1")

    pdf_path = args.pdf
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    logging.info(
        "Parsing %s starting at page %d for %d pages",
        pdf_path,
        args.start_page,
        args.pages,
    )
    pipeline.run_structure_phase(
        pdf_path=pdf_path,
        num_pages=args.pages,
        start_page=args.start_page - 1,
    )

    if args.skip_table_refresh:
        return 0

    logging.info("Rebuilding Markdown tables using %s", JSON_OUTPUT_FILE)
    try:
        processed = rebuild_table_markdown(
            pdf_path=pdf_path,
            json_path=JSON_OUTPUT_FILE,
            overwrite=args.overwrite_table_markdown,
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
