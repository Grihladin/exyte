"""PDF text, structure, and raster helpers built on top of PyMuPDF."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator, Optional

import fitz  # PyMuPDF

from .pdf_filters import HeaderFooterFilter

logger = logging.getLogger(__name__)


class PDFExtractor:
    """High-level convenience wrapper around a PyMuPDF document."""

    def __init__(self, pdf_path: str | Path, remove_headers_footers: bool = True):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        self.doc: Optional[fitz.Document] = None
        self.remove_headers_footers = remove_headers_footers
        self.header_filter = HeaderFooterFilter(self)
        self._open_document()

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def _open_document(self) -> None:
        try:
            self.doc = fitz.open(self.pdf_path)
            logger.info("Opened PDF %s (%d pages)", self.pdf_path, len(self.doc))
        except Exception as exc:
            logger.error("Failed to open PDF %s: %s", self.pdf_path, exc)
            raise

    def _require_document(self) -> fitz.Document:
        if self.doc is None:
            raise ValueError("Document not open")
        return self.doc

    def _get_page(self, page_num: int) -> fitz.Page:
        doc = self._require_document()
        if page_num < 0 or page_num >= len(doc):
            raise ValueError(f"Invalid page number: {page_num}")
        return doc[page_num]

    def close(self) -> None:
        doc = self.doc
        if doc:
            doc.close()
            self.doc = None
            logger.info("Closed PDF document")

    def __enter__(self) -> "PDFExtractor":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    def get_page_count(self) -> int:
        """Return the total number of pages."""
        return len(self._require_document())

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------
    def extract_page_text(self, page_num: int) -> str:
        """Return text for a page, optionally filtered for headers/footers."""
        page = self._get_page(page_num)
        text = page.get_text()
        if self.remove_headers_footers:
            text = self.header_filter.filter_text(text)
        logger.debug("Extracted %d characters from page %d", len(text), page_num + 1)
        return text

    def extract_page_text_with_blocks(self, page_num: int) -> list[dict]:
        """Return low-level text spans (coordinates, font, flags) for a page."""
        page = self._get_page(page_num)
        spans = list(_iter_text_spans(page))
        logger.debug("Extracted %d spans from page %d", len(spans), page_num + 1)
        return spans

    def extract_page_lines_with_fonts(self, page_num: int) -> list[dict]:
        """Return line-level text with approximated font/weight metadata."""
        page = self._get_page(page_num)
        lines = _collect_line_features(page)
        logger.debug("Extracted %d line features from page %d", len(lines), page_num + 1)
        return lines

    def extract_all_text(
        self,
        start_page: int = 0,
        end_page: Optional[int] = None,
    ) -> str:
        """Extract text for a range of pages (defaults to entire document)."""
        doc = self._require_document()
        if end_page is None:
            end_page = len(doc)

        chunks: list[str] = []
        for page_num in range(start_page, end_page):
            chunks.append(self.extract_page_text(page_num))
            if (page_num + 1) % 100 == 0:
                logger.info("Processed %d pages...", page_num + 1)

        combined = "\n\n".join(chunks)
        logger.info(
            "Extracted text from %d pages (%d characters)",
            end_page - start_page,
            len(combined),
        )
        return combined

    # ------------------------------------------------------------------
    # Image helpers
    # ------------------------------------------------------------------
    def get_images_on_page(self, page_num: int) -> list[dict]:
        """List image xrefs present on a page."""
        page = self._get_page(page_num)
        images = [
            {"xref": xref, "index": idx, "page": page_num}
            for idx, (xref, *_rest) in enumerate(page.get_images())
        ]
        logger.debug("Found %d images on page %d", len(images), page_num + 1)
        return images

    def extract_image(self, xref: int) -> dict:
        """Return raw image bytes and metadata for a given xref."""
        try:
            base_image = self._require_document().extract_image(xref)
        except Exception as exc:
            logger.error("Failed to extract image xref=%s: %s", xref, exc)
            raise

        return {
            "data": base_image["image"],
            "extension": base_image["ext"],
            "width": base_image.get("width"),
            "height": base_image.get("height"),
            "colorspace": base_image.get("colorspace"),
        }

    def get_page_rect(self, page_num: int) -> tuple[float, float, float, float]:
        """Return the rectangle describing the entire page."""
        rect = self._get_page(page_num).rect
        return (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))

    def save_page_clip(
        self,
        page_num: int,
        bbox: tuple[float, float, float, float],
        output_path: str | Path,
        scale: float = 2.0,
    ) -> Path:
        """Render a clip of the page to an image."""
        page = self._get_page(page_num)
        rect = fitz.Rect(min(bbox[0], bbox[2]), min(bbox[1], bbox[3]), max(bbox[0], bbox[2]), max(bbox[1], bbox[3]))
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=rect, alpha=False)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(output_path))
        logger.debug("Saved page %d clip to %s", page_num + 1, output_path)
        return output_path


# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def _iter_text_spans(page: fitz.Page) -> Iterator[dict]:
    """Yield flattened span dictionaries for a PyMuPDF page."""
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                yield {
                    "x0": span["bbox"][0],
                    "y0": span["bbox"][1],
                    "x1": span["bbox"][2],
                    "y1": span["bbox"][3],
                    "text": span.get("text", ""),
                    "size": span.get("size"),
                    "font": span.get("font"),
                    "flags": span.get("flags"),
                }


def _collect_line_features(page: fitz.Page) -> list[dict]:
    """Aggregate spans into line-level metadata records."""
    lines: list[dict] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = [span for span in line.get("spans", []) if span.get("text")]
            if not spans:
                continue
            text = "".join(span.get("text", "") for span in spans).strip()
            if not text:
                continue

            sizes = [span.get("size") for span in spans if span.get("size")]
            if not sizes:
                continue

            dominant_span = max(
                spans,
                key=lambda span: len(span.get("text", "").strip()),
            )
            is_bold = any(
                (span.get("flags", 0) & 2)
                or ("Bold" in span.get("font", "") or "Black" in span.get("font", ""))
                for span in spans
            )
            lines.append(
                {
                    "text": text,
                    "max_size": float(max(sizes)),
                    "font": dominant_span.get("font"),
                    "is_bold": is_bold,
                }
            )
    return lines
