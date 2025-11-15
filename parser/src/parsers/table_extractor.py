"""Table extraction using Camelot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import camelot

from ..models import TableData


logger = logging.getLogger(__name__)


class TableExtractor:
    """Extract tables from PDF pages using Camelot."""

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = str(pdf_path)
        self._path_obj = Path(pdf_path)
        if not self._path_obj.exists():
            raise FileNotFoundError(f"PDF not found for table extraction: {pdf_path}")

    def extract_tables(self, page_num: int) -> list[TableData]:
        """Extract table data for a specific 1-indexed page."""
        page_str = str(page_num)
        tables: list[TableData] = []
        # Try lattice first (works best with cell borders), then fall back to stream.
        for flavor in ("lattice", "stream"):
            try:
                result = camelot.read_pdf(
                    self.pdf_path,
                    pages=page_str,
                    flavor=flavor,
                    strip_text='\n',
                )
            except Exception as exc:  # pragma: no cover - Camelot errors depend on PDF content
                logger.debug(
                    "Camelot %s extraction failed on page %s: %s",
                    flavor,
                    page_str,
                    exc,
                )
                continue

            for table in result:
                if table.df.empty:
                    continue
                df = table.df.fillna("")
                headers = [self._clean_cell(cell) for cell in df.iloc[0].tolist()]
                rows = [
                    [self._clean_cell(cell) for cell in df.iloc[row_idx].tolist()]
                    for row_idx in range(1, len(df))
                ]
                max_columns = max(len(headers), max((len(row) for row in rows), default=0))
                non_empty_rows = sum(1 for row in rows if any(cell for cell in row))
                if max_columns <= 1 or non_empty_rows < 1:
                    continue
                accuracy = getattr(table, "accuracy", None)
                tables.append(
                    TableData(
                        headers=headers,
                        rows=rows,
                        page=page_num,
                        accuracy=float(accuracy) if accuracy is not None else None,
                    )
                )

            if tables:
                break  # Prefer the first flavor that produced tables

        if tables:
            logger.debug(
                "Extracted %d table(s) from page %s",
                len(tables),
                page_str,
            )
        return tables

    @staticmethod
    def _clean_cell(value: object) -> str:
        """Normalize cell text for JSON serialization."""
        if value is None:
            return ""
        return str(value).strip()
