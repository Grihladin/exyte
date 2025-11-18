"""Utilities for extracting table content from PDFs and encoding it as Markdown."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Sequence

import pdfplumber

logger = logging.getLogger(__name__)

_TABLE_SETTINGS_CANDIDATES = (
    {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
    {"vertical_strategy": "text", "horizontal_strategy": "text"},
    None,
)


def extract_table_markdown_from_page(
    page: "pdfplumber.page.Page",
    bbox: Sequence[float],
) -> str | None:
    """Crop a pdfplumber page to bbox and return Markdown if a table is detected."""
    rows = _extract_rows_from_page(page, bbox)
    if not rows:
        return None
    return rows_to_markdown(rows)


def extract_table_markdown_from_pdf(
    pdf_path: str | Path,
    page_index: int,
    bbox: Sequence[float],
) -> str | None:
    """Open the PDF, extract the requested page region, and convert to Markdown."""
    pdf_path = str(pdf_path)
    try:
        with pdfplumber.open(pdf_path) as pdf_doc:
            if page_index < 0 or page_index >= len(pdf_doc.pages):
                logger.warning(
                    "pdfplumber page index %s is out of bounds for %s",
                    page_index,
                    pdf_path,
                )
                return None
            page = pdf_doc.pages[page_index]
            return extract_table_markdown_from_page(page, bbox)
    except Exception as exc:  # pragma: no cover - pdfplumber internals
        logger.warning("Failed to extract table via pdfplumber: %s", exc)
        return None


def rows_to_markdown(rows: Sequence[Sequence[str]]) -> str | None:
    """Convert normalized rows into a GitHub-flavored Markdown table."""
    cleaned = _normalize_rows(rows)
    if len(cleaned) < 2:
        return None

    max_cols = max(len(row) for row in cleaned)
    padded_rows = [_pad_row(row, max_cols) for row in cleaned]

    header = padded_rows[0]
    body = padded_rows[1:]
    if not any(cell for cell in header) or not any(
        any(cell for cell in row) for row in body
    ):
        return None

    header_line = "| " + " | ".join(header) + " |"
    divider_line = "| " + " | ".join("---" for _ in header) + " |"
    body_lines = ["| " + " | ".join(row) + " |" for row in body]
    return "\n".join([header_line, divider_line, *body_lines]).strip()


def _extract_rows_from_page(
    page: "pdfplumber.page.Page",
    bbox: Sequence[float],
) -> List[List[str]]:
    """Crop the page to bbox and return table rows using relaxed settings."""
    cleaned_bbox = _clean_bbox(bbox)
    clip = page.crop(cleaned_bbox)
    raw_table: list[list[str | None]] | None = None
    for settings in _TABLE_SETTINGS_CANDIDATES:
        raw_table = clip.extract_table(table_settings=settings)
        if raw_table:
            break

    if not raw_table:
        return []

    rows: List[List[str]] = []
    for raw_row in raw_table:
        normalized_row = [_normalize_cell(cell) for cell in raw_row or []]
        if any(normalized_row):
            rows.append(normalized_row)
    return rows


def _normalize_cell(cell: str | None) -> str:
    if cell is None:
        return ""
    value = str(cell).strip().replace("\n", " ")
    return " ".join(value.split())


def _normalize_rows(rows: Sequence[Sequence[str]]) -> List[List[str]]:
    normalized: List[List[str]] = []
    for row in rows:
        normalized_row = [_normalize_cell(cell) for cell in row]
        normalized.append(normalized_row)
    return normalized


def _pad_row(row: Sequence[str], width: int) -> List[str]:
    padded = list(row)
    if len(padded) < width:
        padded.extend([""] * (width - len(padded)))
    return padded


def _clean_bbox(bbox: Sequence[float]) -> tuple[float, float, float, float]:
    if len(bbox) != 4:
        raise ValueError(f"Expected bbox with four values, got {bbox!r}")
    x0, y0, x1, y1 = bbox
    return (
        float(min(x0, x1)),
        float(min(y0, y1)),
        float(max(x0, x1)),
        float(max(y0, y1)),
    )
