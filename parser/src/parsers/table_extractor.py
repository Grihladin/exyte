"""Table detection and snapshotting helpers powered by DeepSeek OCR."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Optional

if TYPE_CHECKING:  # pragma: no cover - runtime only
    from .pdf_extractor import PDFExtractor

from ..models import TableData
from ..utils.deepseek_ocr import DeepSeekOCR
from ..utils.tables import extract_table_labels


logger = logging.getLogger(__name__)


class TableExtractor:
    """Detect tables on PDF pages, snapshot them, and record metadata."""

    def __init__(
        self,
        pdf_path: str | Path,
        table_images_dir: str | Path,
        table_regions_file: str | Path | None = None,
        ocr_client: DeepSeekOCR | None = None,
    ):
        self.pdf_path = str(pdf_path)
        self._path_obj = Path(pdf_path)
        if not self._path_obj.exists():
            raise FileNotFoundError(f"PDF not found for table extraction: {pdf_path}")

        self.images_dir = Path(table_images_dir)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self._image_counter = 0

        self._region_overrides = self._load_region_overrides(table_regions_file)
        self.ocr_client = ocr_client

    def extract_tables(
        self,
        page_num: int,
        pdf_extractor: Optional["PDFExtractor"] = None,
        page_text: str | None = None,
    ) -> list[TableData]:
        """Detect table regions for a specific (1-indexed) page and save images."""
        if pdf_extractor is None:
            logger.warning("PDFExtractor instance required for table snapshotting.")
            return []

        page_index = page_num - 1
        regions = list(self._region_overrides.get(page_num, []))
        region_source = "precomputed"

        if not regions:
            regions = self._estimate_regions(page_index, pdf_extractor, page_text)
            region_source = "page-heuristic"

        if not regions:
            logger.debug("No table regions found for page %s", page_num)
            return []

        tables: list[TableData] = []
        for bbox in regions:
            relative_path, abs_path = self._save_table_image(
                pdf_extractor, page_index, page_num, bbox
            )
            headers: list[str] = []
            rows: list[list[str]] = []
            if abs_path:
                headers, rows = self._extract_table_content(abs_path)

            tables.append(
                TableData(
                    headers=headers,
                    rows=rows,
                    page=page_num,
                    accuracy=None,
                    image_path=relative_path,
                    bbox=bbox,
                )
            )

        logger.info(
            "Saved %d table snapshot(s) on page %s via %s detection",
            len(tables),
            page_num,
            region_source,
        )
        return tables

    def _estimate_regions(
        self,
        page_index: int,
        pdf_extractor: "PDFExtractor",
        page_text: str | None,
    ) -> list[tuple[float, float, float, float]]:
        """Fallback heuristic that treats the whole page as table area per label."""
        labels = extract_table_labels(page_text)
        count = max(len(labels), 1)
        try:
            page_rect = pdf_extractor.get_page_rect(page_index)
        except Exception as exc:  # pragma: no cover - depends on PyMuPDF state
            logger.warning(
                "Failed to read page bounds for page %s: %s",
                page_index + 1,
                exc,
            )
            return []

        return [page_rect for _ in range(count)]

    def _save_table_image(
        self,
        pdf_extractor: "PDFExtractor",
        page_index: int,
        page_num: int,
        bbox: tuple[float, float, float, float],
    ) -> tuple[str | None, Path | None]:
        """Crop the PDF page for the table bbox and save it as an image."""
        filename = self._build_image_filename(page_num)
        image_path = self.images_dir / filename
        try:
            pdf_extractor.save_page_clip(page_index, bbox, image_path)
        except Exception as exc:  # pragma: no cover - depends on PDF content
            logger.warning(
                "Failed to save table image for page %s (%s): %s",
                page_num,
                filename,
                exc,
            )
            return None, None

        try:
            relative_path = image_path.relative_to(self.images_dir.parent)
        except ValueError:
            relative_path = image_path.name
        return str(relative_path), image_path

    def _build_image_filename(self, page_num: int) -> str:
        """Generate deterministic output filenames for saved tables."""
        self._image_counter += 1
        return f"table_p{page_num:04d}_{self._image_counter:05d}.png"

    def _load_region_overrides(
        self,
        table_regions_file: str | Path | None,
    ) -> dict[int, list[tuple[float, float, float, float]]]:
        """Load optional region overrides produced by an external detector."""
        if not table_regions_file:
            return {}

        path = Path(table_regions_file)
        if not path.exists():
            return {}

        try:
            raw_data = json.loads(path.read_text())
        except Exception as exc:
            logger.warning("Failed to parse table region file %s: %s", path, exc)
            return {}

        region_map: dict[int, list[tuple[float, float, float, float]]] = {}
        for page_key, boxes in raw_data.items():
            try:
                page_num = int(page_key)
            except (TypeError, ValueError):
                logger.debug("Ignoring invalid page key in table regions: %r", page_key)
                continue

            normalized_boxes = [
                bbox for bbox in (self._normalize_bbox(box) for box in boxes) if bbox
            ]
            if normalized_boxes:
                region_map[page_num] = normalized_boxes

        if region_map:
            logger.info(
                "Loaded region overrides for %d page(s) from %s",
                len(region_map),
                path,
            )
        return region_map

    @staticmethod
    def _normalize_bbox(box: Iterable[float] | None) -> tuple[float, float, float, float] | None:
        """Convert any bbox-like iterable to a sorted tuple."""
        if not box:
            return None

        coords = list(box)
        if len(coords) != 4:
            return None

        try:
            x0, y0, x1, y1 = (float(value) for value in coords)
        except (TypeError, ValueError):
            return None

        x_min, x_max = sorted((x0, x1))
        y_min, y_max = sorted((y0, y1))

        if x_min == x_max or y_min == y_max:
            return None

        return (x_min, y_min, x_max, y_max)

    def _extract_table_content(
        self,
        image_path: Path | None,
    ) -> tuple[list[str], list[list[str]]]:
        """Run OCR on the saved table image to populate rows/headers."""
        if not image_path or not self.ocr_client:
            return [], []
        try:
            ocr_table = self.ocr_client.extract_table(image_path)
        except Exception as exc:  # pragma: no cover - model/runtime specific
            logger.warning("DeepSeek OCR failed on %s: %s", image_path, exc)
            return [], []
        return ocr_table.headers, ocr_table.rows
