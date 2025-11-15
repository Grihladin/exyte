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
        # Lattice is better for tables with clear borders/lines
        # Stream is better for tables without borders (whitespace-separated)
        for flavor in ("lattice", "stream"):
            try:
                # Configure Camelot parameters for better extraction
                kwargs = {
                    "pages": page_str,
                    "flavor": flavor,
                    "strip_text": '\n',  # Remove newlines from cells
                }
                
                if flavor == "lattice":
                    # Lattice-specific parameters for better grid detection
                    kwargs.update({
                        "line_scale": 40,  # Detect shorter lines (default: 15)
                        "process_background": True,  # Process background lines
                        "line_tol": 2,  # Line tolerance for joining lines
                    })
                else:
                    # Stream-specific parameters for whitespace-based detection
                    kwargs.update({
                        "edge_tol": 50,  # Tolerance for detecting table edges (default: 50)
                        "row_tol": 2,  # Tolerance for grouping rows (default: 2)
                        "column_tol": 0,  # Tolerance for grouping columns
                    })
                
                result = camelot.read_pdf(self.pdf_path, **kwargs)
                
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
                
                # Extract headers and rows
                headers = [self._clean_cell(cell) for cell in df.iloc[0].tolist()]
                rows = [
                    [self._clean_cell(cell) for cell in df.iloc[row_idx].tolist()]
                    for row_idx in range(1, len(df))
                ]
                
                # Quality checks
                max_columns = max(len(headers), max((len(row) for row in rows), default=0))
                non_empty_rows = sum(1 for row in rows if any(cell.strip() for cell in row))
                
                # Skip low-quality extractions
                if max_columns <= 1:
                    logger.debug(f"Skipping single-column table on page {page_num}")
                    continue
                    
                if non_empty_rows < 1:
                    logger.debug(f"Skipping empty table on page {page_num}")
                    continue
                
                # Check accuracy if available
                accuracy = getattr(table, "accuracy", None)
                if accuracy is not None and accuracy < 50:
                    logger.debug(f"Skipping low-accuracy table (accuracy={accuracy:.1f}) on page {page_num}")
                    continue
                
                tables.append(
                    TableData(
                        headers=headers,
                        rows=rows,
                        page=page_num,
                        accuracy=float(accuracy) if accuracy is not None else None,
                    )
                )

            if tables:
                logger.info(
                    "Extracted %d table(s) using %s on page %s (avg accuracy: %.1f)",
                    len(tables),
                    flavor,
                    page_str,
                    sum(t.accuracy or 0 for t in tables) / len(tables)
                )
                break  # Prefer the first flavor that produced tables

        if not tables:
            logger.debug(f"No tables extracted from page {page_str}")
            
        return tables

    @staticmethod
    def _clean_cell(value: object) -> str:
        """Normalize cell text for JSON serialization."""
        if value is None:
            return ""
        return str(value).strip()
