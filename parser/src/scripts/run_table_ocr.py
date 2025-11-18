"""Apply DeepSeek OCR to existing table images and update the JSON output."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Sequence

from src.config import (
    JSON_OUTPUT_FILE,
    OUTPUT_DIR,
    TABLE_IMAGES_DIR,
    DEEPSEEK_OCR_MODEL,
    DEEPSEEK_OCR_DEVICE,
    DEEPSEEK_OCR_MAX_TOKENS,
)
from src.utils.deepseek_ocr import DeepSeekOCR

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run DeepSeek OCR on saved table images and update parsed_document.json."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=JSON_OUTPUT_FILE,
        help="Path to the parsed_document.json file.",
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
        help="Re-run OCR even if headers/rows already exist.",
    )
    parser.add_argument(
        "--model",
        default=DEEPSEEK_OCR_MODEL,
        help="DeepSeek OCR model name (default from config).",
    )
    parser.add_argument(
        "--device",
        default=DEEPSEEK_OCR_DEVICE,
        help="Torch device override (default: auto-detect).",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=DEEPSEEK_OCR_MAX_TOKENS,
        help="Maximum tokens to generate for each table image.",
    )
    return parser.parse_args(argv)


def should_process_table(entry: dict, overwrite: bool) -> bool:
    if overwrite:
        return True
    headers = entry.get("headers") or []
    rows = entry.get("rows") or []
    return not headers and not rows


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.source.exists():
        raise SystemExit(f"JSON file not found: {args.source}")

    with args.source.open("r", encoding="utf-8") as f:
        document = json.load(f)

    tables = document.get("tables", {})
    if not tables:
        logging.info("No tables found in %s", args.source)
        return 0

    table_filter = set(args.tables) if args.tables else None

    ocr = DeepSeekOCR(
        model_name=args.model,
        device=args.device,
        max_new_tokens=args.max_new_tokens,
    )

    processed = 0
    for table_id, entry in tables.items():
        if table_filter and table_id not in table_filter:
            continue
        if not should_process_table(entry, args.overwrite):
            continue

        image_rel = entry.get("image_path")
        if not image_rel:
            logging.warning("Table %s is missing image_path; skipping", table_id)
            continue

        image_path = (OUTPUT_DIR / image_rel).resolve()
        if not image_path.exists():
            logging.warning("Image for table %s not found at %s", table_id, image_path)
            continue

        logging.info("Running OCR for table %s (%s)", table_id, image_path)
        ocr_table = ocr.extract_table(image_path)
        entry["headers"] = ocr_table.headers
        entry["rows"] = ocr_table.rows
        processed += 1

    if processed == 0:
        logging.info("No tables required OCR updates.")
        return 0

    with args.source.open("w", encoding="utf-8") as f:
        json.dump(document, f, indent=2)

    logging.info("Updated %d table(s) in %s", processed, args.source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

