"""CLI wrapper for rebuilding table Markdown using pdfplumber."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from src.config import (
    JSON_OUTPUT_FILE,
    DEFAULT_PDF_PATH,
)
from src.utils.table_markdown import rebuild_table_markdown

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild Markdown tables in parsed_document.json using pdfplumber."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=JSON_OUTPUT_FILE,
        help="Path to the parsed_document.json file.",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=DEFAULT_PDF_PATH,
        help="Path to the source PDF (used for extracting table text).",
    )
    parser.add_argument(
        "--tables",
        nargs="*",
        default=None,
        help="Specific table IDs to process (default: process all tables).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Rebuild Markdown even if it already exists.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        processed = rebuild_table_markdown(
            pdf_path=args.pdf,
            json_path=args.source,
            table_ids=args.tables,
            overwrite=args.overwrite,
        )
    except FileNotFoundError as exc:
        raise SystemExit(str(exc))

    if processed == 0:
        logging.info("No tables required Markdown updates.")
    else:
        logging.info("Updated %d table(s) in %s", processed, args.source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
