"""Helpers for rebuilding Markdown tables within parsed_document.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Mapping, Sequence

import pdfplumber

from .pdf_tables import extract_table_markdown_from_page

logger = logging.getLogger(__name__)

__all__ = ["rebuild_table_markdown"]


def rebuild_table_markdown(
    pdf_path: str | Path,
    json_path: str | Path,
    *,
    table_ids: Sequence[str] | None = None,
    overwrite: bool = False,
    log: logging.Logger | None = None,
) -> int:
    """
    Rebuild Markdown table content inside parsed_document.json.

    Args:
        pdf_path: Path to the source PDF.
        json_path: Path to parsed_document.json (updated in-place).
        table_ids: Optional iterable of specific table IDs to refresh.
        overwrite: When False, only refresh tables missing Markdown.
        log: Optional logger to use for status messages.

    Returns:
        The number of tables updated.
    """

    log = log or logger
    pdf_path = Path(pdf_path)
    json_path = Path(json_path)

    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    with json_path.open("r", encoding="utf-8") as f:
        document = json.load(f)

    tables: Mapping[str, dict] = document.get("tables") or {}
    if not tables:
        log.info("No tables found in %s", json_path)
        return 0

    table_filter = set(table_ids) if table_ids else None
    processed = 0

    with pdfplumber.open(str(pdf_path)) as pdf_doc:
        page_count = len(pdf_doc.pages)

        for table_id, entry in tables.items():
            if table_filter and table_id not in table_filter:
                continue
            if not _should_process_table(entry, overwrite):
                continue

            page_number = entry.get("page")
            bbox = entry.get("bbox")
            if page_number is None or bbox is None:
                log.warning(
                    "Table %s is missing page/bbox metadata; skipping.", table_id
                )
                continue

            page_index = int(page_number) - 1
            if page_index < 0 or page_index >= page_count:
                log.warning(
                    "Table %s references invalid page %s (document has %s pages).",
                    table_id,
                    page_number,
                    page_count,
                )
                continue

            page = pdf_doc.pages[page_index]
            markdown = extract_table_markdown_from_page(page, bbox)
            if not markdown:
                log.warning(
                    "Unable to extract Markdown for table %s on page %s.",
                    table_id,
                    page_number,
                )
                continue

            entry["markdown"] = markdown
            processed += 1

    if processed:
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(document, f, indent=2)

    return processed


def _should_process_table(entry: Mapping[str, object], overwrite: bool) -> bool:
    if overwrite:
        return True
    value = entry.get("markdown") if entry else None
    if isinstance(value, str):
        return not value.strip()
    return not value
