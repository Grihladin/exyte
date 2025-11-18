"""Table detection and snapshotting helpers backed by pdfplumber."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Optional

import pdfplumber

if TYPE_CHECKING:  # pragma: no cover - runtime only
    from .pdf_extractor import PDFExtractor

from ..models import TableData
from ..utils.pdf_tables import extract_table_markdown_from_page
from ..utils.tables import extract_table_labels


logger = logging.getLogger(__name__)


class TableExtractor:
    """Detect tables on PDF pages, snapshot them, and record metadata."""

    def __init__(
        self,
        pdf_path: str | Path,
        table_images_dir: str | Path,
        table_regions_file: str | Path | None = None,
    ):
        self.pdf_path = str(pdf_path)
        self._path_obj = Path(pdf_path)
        if not self._path_obj.exists():
            raise FileNotFoundError(f"PDF not found for table extraction: {pdf_path}")

        self.images_dir = Path(table_images_dir)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self._image_counter = 0

        self._region_overrides = self._load_region_overrides(table_regions_file)

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

        # Extract table labels from the page text for naming
        table_labels = extract_table_labels(page_text) if page_text else []

        pdfplumber_doc = None
        pdfplumber_page = None
        try:
            pdfplumber_doc = pdfplumber.open(self.pdf_path)
            pdfplumber_page = pdfplumber_doc.pages[page_index]
        except Exception as exc:
            logger.warning(
                "pdfplumber is unavailable for page %s: %s",
                page_num,
                exc,
            )
        tables: list[TableData] = []
        for idx, bbox in enumerate(regions):
            # Get the table label for this specific table
            table_label = table_labels[idx] if idx < len(table_labels) else None

            relative_path, _ = self._save_table_image(
                pdf_extractor, page_index, page_num, bbox, table_label
            )
            markdown = None
            if pdfplumber_page is not None:
                markdown = extract_table_markdown_from_page(pdfplumber_page, bbox)

            # Extract table notes/info below the table
            table_info = self._extract_table_notes(
                pdf_extractor._get_page(page_index), bbox, page_text
            )
            
            # Extract table name/title (text between TABLE number and the table itself)
            table_name = self._extract_table_name(
                pdf_extractor._get_page(page_index), bbox, table_label, page_num, idx
            )

            tables.append(
                TableData(
                    markdown=markdown,
                    page=page_num,
                    accuracy=None,
                    image_path=relative_path,
                    bbox=bbox,
                    table_info=table_info,
                    table_name=table_name,
                )
            )

        logger.info(
            "Saved %d table snapshot(s) on page %s via %s detection",
            len(tables),
            page_num,
            region_source,
        )
        if pdfplumber_doc:
            pdfplumber_doc.close()
        return tables

    def _estimate_regions(
        self,
        page_index: int,
        pdf_extractor: "PDFExtractor",
        page_text: str | None,
    ) -> list[tuple[float, float, float, float]]:
        """Use PyMuPDF's built-in table detection to find actual table boundaries."""
        try:
            import fitz

            # First, check if the page actually contains TABLE labels (not just FIGURE)
            if not page_text or not self._page_has_table_labels(page_text):
                logger.debug(
                    "Page %s: No TABLE labels found (skipping table detection)",
                    page_index + 1,
                )
                return []

            # Get the page from the PDF
            page = pdf_extractor._get_page(page_index)

            # Use PyMuPDF's find_tables() to detect table regions
            tables = page.find_tables()

            if not tables or not tables.tables:
                logger.debug(
                    "PyMuPDF find_tables found no tables on page %s",
                    page_index + 1,
                )
                return []

            # Extract bounding boxes from detected tables
            all_regions = []
            for table in tables:
                bbox = table.bbox
                # bbox is already a tuple (x0, y0, x1, y1) or a Rect object
                if hasattr(bbox, "x0"):
                    # It's a Rect object
                    region = (
                        float(bbox.x0),
                        float(bbox.y0),
                        float(bbox.x1),
                        float(bbox.y1),
                    )
                else:
                    # It's already a tuple
                    region = tuple(float(x) for x in bbox)

                all_regions.append(region)

            # Filter out regions that are likely figures, not tables
            regions = self._filter_out_figures(page, all_regions, page_text)

            for region in regions:
                logger.debug(
                    "Page %s: Found table at bbox %s",
                    page_index + 1,
                    region,
                )

            return regions

        except Exception as exc:  # pragma: no cover - depends on PyMuPDF state
            logger.warning(
                "Failed to detect tables on page %s: %s",
                page_index + 1,
                exc,
            )
            return []

    def _page_has_table_labels(self, page_text: str) -> bool:
        """Check if page contains TABLE labels (not FIGURE labels)."""
        import re

        # Look for TABLE keywords with optional prefix like [F] or [A]
        # Pattern matches: TABLE, [F] TABLE, [A] TABLE, [BS] TABLE, etc.
        table_pattern = re.compile(
            r"(?:\[[A-Z]+\]\s+)?TABLE\s+[\d\w\.\-\(\)]+", re.IGNORECASE
        )

        # Check if there are TABLE labels
        table_matches = table_pattern.findall(page_text)

        if not table_matches:
            return False

        # Additional check: make sure we're not just finding "TABLE" in body text
        # Real table labels usually appear on their own line or at the start of a line
        lines = page_text.split("\n")
        has_real_table = False
        for line in lines:
            line_stripped = line.strip()
            # Check if line starts with TABLE or [X] TABLE
            if re.match(
                r"^(?:\[[A-Z]+\]\s+)?TABLE\s+[\d\w\.\-\(\)]+",
                line_stripped,
                re.IGNORECASE,
            ):
                has_real_table = True
                break

        return has_real_table

    def _filter_out_figures(
        self,
        page: "fitz.Page",
        regions: list[tuple[float, float, float, float]],
        page_text: str | None,
    ) -> list[tuple[float, float, float, float]]:
        """Filter out regions that are likely figures rather than tables."""
        import re

        if not page_text or not regions:
            return regions

        # Extract positions of TABLE and FIGURE labels with their Y coordinates
        table_positions = []
        figure_positions = []

        # Get text blocks with positions
        try:
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:  # Not a text block
                    continue

                for line in block.get("lines", []):
                    line_text = ""
                    y_pos = line.get("bbox", [0, 0, 0, 0])[1]  # Get y0 coordinate

                    for span in line.get("spans", []):
                        line_text += span.get("text", "")

                    line_text = line_text.strip()

                    # Check if this line contains a TABLE label
                    if re.match(
                        r"^(?:\[[A-Z]+\]\s+)?TABLE\s+[\d\w\.\-\(\)]+",
                        line_text,
                        re.IGNORECASE,
                    ):
                        table_positions.append(y_pos)

                    # Check if this line contains a FIGURE label
                    elif re.match(
                        r"^(?:\[[A-Z]+\]\s+)?FIGURE\s+[\d\w\.\-\(\)]+",
                        line_text,
                        re.IGNORECASE,
                    ):
                        figure_positions.append(y_pos)

        except Exception as exc:
            logger.debug("Could not extract text positions for filtering: %s", exc)
            return regions

        # If we don't have any TABLE labels or FIGURE labels, return all regions
        if not table_positions:
            return regions

        # Filter regions: keep only those closer to TABLE labels than to FIGURE labels
        filtered_regions = []
        for region in regions:
            region_y = region[1]  # y0 of the region

            # Find closest TABLE label
            closest_table_dist = min(
                (abs(region_y - table_y) for table_y in table_positions),
                default=float("inf"),
            )

            # Find closest FIGURE label
            closest_figure_dist = min(
                (abs(region_y - fig_y) for fig_y in figure_positions),
                default=float("inf"),
            )

            # Keep region if it's closer to a TABLE than to a FIGURE
            # or if there are no FIGURE labels at all
            if not figure_positions or closest_table_dist < closest_figure_dist:
                filtered_regions.append(region)
            else:
                logger.debug(
                    "Filtered out region %s (closer to FIGURE than TABLE)", region
                )

        return filtered_regions

    def _save_table_image(
        self,
        pdf_extractor: "PDFExtractor",
        page_index: int,
        page_num: int,
        bbox: tuple[float, float, float, float],
        table_label: str | None = None,
    ) -> tuple[str | None, Path | None]:
        """Crop the PDF page for the table bbox and save it as an image."""
        filename = self._build_image_filename(page_num, table_label)
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

    def _build_image_filename(
        self, page_num: int, table_label: str | None = None
    ) -> str:
        """Generate output filenames like table_415.6.5_p0431.png from TABLE labels."""
        import re

        if table_label:
            # Extract the table number from labels like:
            # "TABLE 1608.2", "[F] TABLE 415.6.5", "[A] Table 307.1(1)"
            match = re.search(
                r"(?:\[[A-Z]+\]\s+)?TABLE\s+([\d\w\.\-\(\)]+)",
                table_label,
                re.IGNORECASE,
            )
            if match:
                table_num = match.group(1)
                # Clean up the table number (remove any problematic characters for filenames)
                table_num = re.sub(r"[^\w\.\-\(\)]", "_", table_num)
                return f"table_{table_num}_p{page_num:04d}.png"
                return f"table_{table_num}_p{page_num:04d}.png"

        # Fallback to counter-based naming if no label found
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
    def _normalize_bbox(
        box: Iterable[float] | None,
    ) -> tuple[float, float, float, float] | None:
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

    def _extract_table_notes(
        self,
        page: "fitz.Page",
        table_bbox: tuple[float, float, float, float],
        page_text: str | None,
    ) -> list[str]:
        """Extract notes and info text below a table (For SI:, a., b., etc.)."""
        import re

        if not page_text:
            return []

        try:
            # Get text blocks with their positions
            text_dict = page.get_text("dict")

            # Table bottom Y coordinate
            table_bottom = table_bbox[3]

            # Collect text that appears below the table (within ~100 points)
            # and looks like table notes
            notes = []
            note_y_threshold = table_bottom + 100  # Look 100 points below table

            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:  # Not a text block
                    continue

                for line in block.get("lines", []):
                    line_y = line.get("bbox", [0, 0, 0, 0])[1]  # y0 coordinate

                    # Skip if line is above table or too far below
                    if line_y < table_bottom or line_y > note_y_threshold:
                        continue

                    # Build line text
                    line_text = ""
                    for span in line.get("spans", []):
                        line_text += span.get("text", "")

                    line_text = line_text.strip()

                    # Check if this looks like a table note:
                    # - Starts with "For SI:", "For Imperial:", etc.
                    # - Starts with a lowercase letter followed by period (a., b., c.)
                    # - Starts with a number followed by period (1., 2., 3.)
                    if re.match(r"^(?:For\s+[A-Z]+:|[a-z]\.|[0-9]+\.)", line_text):
                        notes.append(line_text)
                    # Sometimes notes continue on next line without prefix
                    elif notes and len(line_text) > 10:
                        # If previous line was a note and this looks like continuation
                        # (doesn't start with TABLE, FIGURE, or section number)
                        if not re.match(
                            r"^(?:TABLE|FIGURE|SECTION|\d+\.\d+)",
                            line_text,
                            re.IGNORECASE,
                        ):
                            # Append to previous note if it's close
                            if line_y - table_bottom < 80:
                                notes[-1] = notes[-1] + " " + line_text

            return notes

        except Exception as exc:
            logger.debug("Could not extract table notes: %s", exc)
            return []

    def _extract_table_name(
        self,
        page: "fitz.Page",
        table_bbox: tuple[float, float, float, float],
        table_label: str | None,
        page_num: int,
        idx: int,
    ) -> str:
        """Extract the table title/name (text between TABLE number and table itself).
        Always returns a formatted name with TABLE [NUMBER] prefix."""
        import re
        
        # Extract table number from label
        table_number = None
        if table_label:
            match = re.search(
                r'(?:\[[A-Z]+\]\s+)?TABLE\s+([\d\w\.\-\(\)]+)',
                table_label,
                re.IGNORECASE
            )
            if match:
                table_number = match.group(1)
        
        # If no table number found, generate one
        if not table_number:
            table_number = f"{page_num}.{idx + 1}"
        
        # Try to extract the title
        title = None
        
        if table_label:
            try:
                # Get text blocks with their positions
                text_dict = page.get_text("dict")
                
                # Table top Y coordinate
                table_top = table_bbox[1]
                
                # First, find the Y position and full text of the TABLE label line
                label_y = None
                label_line = None
                for block in text_dict.get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    
                    for line in block.get("lines", []):
                        line_text = ""
                        for span in line.get("spans", []):
                            line_text += span.get("text", "")
                        
                        line_text_stripped = line_text.strip()
                        
                        # Check if this is the TABLE label line
                        if re.search(
                            r'(?:\[[A-Z]+\]\s+)?TABLE\s+[\d\w\.\-\(\)]+',
                            line_text_stripped,
                            re.IGNORECASE
                        ):
                            label_y = line.get("bbox", [0, 0, 0, 0])[1]
                            label_line = line_text_stripped
                            break
                    
                    if label_y is not None:
                        break
                
                if label_y is not None and label_line is not None:
                    # Check if the TABLE label line already contains the title
                    # e.g., "TABLE 1006.3.3 MINIMUM NUMBER OF EXITS..."
                    match = re.match(
                        r'^(?:\[[A-Z]+\]\s+)?TABLE\s+[\d\w\.\-\(\)]+\s+(.+)$',
                        label_line,
                        re.IGNORECASE
                    )
                    if match:
                        potential_title = match.group(1).strip()
                        # Only accept if it's mostly uppercase (indicates a title, not body text)
                        if len(potential_title) > 0 and sum(1 for c in potential_title if c.isupper()) / len(potential_title.replace(' ', '')) > 0.5:
                            title = potential_title
                    
                    # If no title found yet, look for title text immediately after the TABLE label
                    if not title:
                        name_lines = []
                        max_title_y = label_y + 30  # Only look within 30 points
                        
                        for block in text_dict.get("blocks", []):
                            if block.get("type") != 0:
                                continue
                            
                            for line in block.get("lines", []):
                                line_y = line.get("bbox", [0, 0, 0, 0])[1]
                                
                                # Text must be after the label but not too far
                                if line_y <= label_y or line_y >= min(max_title_y, table_top):
                                    continue
                                
                                # Build line text
                                line_text = ""
                                for span in line.get("spans", []):
                                    line_text += span.get("text", "")
                                
                                line_text = line_text.strip()
                                
                                # Skip if empty
                                if not line_text:
                                    continue
                                
                                # Skip if it looks like body text or section numbers
                                if re.match(r'^\d+\.\d+', line_text):
                                    continue
                                
                                # Only accept if it's mostly uppercase and looks like a title
                                if len(line_text.replace(' ', '')) > 0:
                                    uppercase_ratio = sum(1 for c in line_text if c.isupper()) / len(line_text.replace(' ', ''))
                                    if uppercase_ratio > 0.5:  # More than 50% uppercase
                                        name_lines.append(line_text)
                        
                        if name_lines:
                            # Join multi-line titles
                            full_title = " ".join(name_lines)
                            # Clean up: remove any trailing section numbers or body text
                            full_title = re.sub(r'\s+\d+\.\d+.*$', '', full_title)
                            title = full_title.strip()
                
            except Exception as exc:
                logger.debug("Could not extract table name: %s", exc)
        
        # Build the final formatted name
        if title:
            return f"TABLE {table_number} {title}"
        else:
            return f"TABLE {table_number}"
