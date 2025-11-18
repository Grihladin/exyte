"""Header/footer filtering for PDF extraction."""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .pdf_extractor import PDFExtractor

logger = logging.getLogger(__name__)


class HeaderFooterFilter:
    """Detect and filter repeated headers/footers from PDF text."""

    def __init__(self, extractor: "PDFExtractor") -> None:
        self.extractor = extractor
        self.common_headers_footers: set[str] = set()

    def ensure_detected(self) -> None:
        if not self.common_headers_footers and self.extractor.doc:
            self.detect_common_patterns()

    def detect_common_patterns(self, sample_size: int = 10) -> None:
        doc = self.extractor.doc
        if not doc or not self.extractor.remove_headers_footers:
            return

        total_pages = len(doc)
        step = max(1, total_pages // sample_size)
        sample_pages = range(0, min(total_pages, sample_size * step), step)
        page_blocks = []
        for page_num in sample_pages:
            try:
                blocks = self.extractor.extract_page_text_with_blocks(page_num)
            except Exception:  # pragma: no cover - best effort logging
                continue
            top_blocks = [b for b in blocks if b["y0"] < 100]
            bottom_blocks = [b for b in blocks if b["y0"] > 700]
            page_blocks.append(
                {
                    "top": " ".join(b["text"] for b in top_blocks),
                    "bottom": " ".join(b["text"] for b in bottom_blocks),
                }
            )

        if not page_blocks:
            return

        threshold = len(page_blocks) * 0.5
        top_texts = [p["top"] for p in page_blocks if p["top"].strip()]
        if top_texts:
            self.common_headers_footers.update(
                text for text, count in Counter(top_texts).items() if count >= threshold
            )
        bottom_texts = [p["bottom"] for p in page_blocks if p["bottom"].strip()]
        if bottom_texts:
            self.common_headers_footers.update(
                text
                for text, count in Counter(bottom_texts).items()
                if count >= threshold
            )

        copyright_patterns = [
            "Copyright © 2020 ICC. ALL RIGHTS RESERVED.",
            "INTERNATIONAL CODE COUNCIL",
            "2021 INTERNATIONAL BUILDING CODE®",
        ]
        self.common_headers_footers.update(copyright_patterns)
        if self.common_headers_footers:
            logger.info(
                "Detected %d common header/footer patterns",
                len(self.common_headers_footers),
            )

    def filter_text(self, text: str) -> str:
        if not self.extractor.remove_headers_footers or not text:
            return text
        self.ensure_detected()
        if not self.common_headers_footers:
            return text

        text = self._strip_copyright_blocks(text)
        lines = text.split("\n")
        filtered_lines = []
        prev_line_was_chapter = False
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            if any(
                pattern in line_stripped or line_stripped in pattern
                for pattern in self.common_headers_footers
            ):
                prev_line_was_chapter = False
                continue
            # Skip duplicate chapter headers (e.g., repeated at top of pages)
            # Only remove if this is NOT the first occurrence of a chapter header
            if line_stripped.startswith("CHAPTER ") and prev_line_was_chapter:
                continue
            if (
                line_stripped
                and len(line_stripped) < 5
                and line_stripped.replace("-", "").replace("®", "").isdigit()
            ):
                prev_line_was_chapter = False
                continue
            filtered_lines.append(line)
            prev_line_was_chapter = line_stripped.startswith("CHAPTER ")
        return "\n".join(filtered_lines)

    def _strip_copyright_blocks(self, text: str) -> str:
        copyright_start_patterns = ["Copyright © 2020 ICC", "Copyright © 2020 ICC."]
        copyright_end_patterns = ["101167924", "THEREUNDER.", "PENALTIES THEREUNDER"]
        for start_pattern in copyright_start_patterns:
            while start_pattern in text:
                start_idx = text.find(start_pattern)
                end_idx = -1
                for end_pattern in copyright_end_patterns:
                    temp_idx = text.find(end_pattern, start_idx)
                    if temp_idx != -1:
                        end_idx = temp_idx + len(end_pattern)
                        while end_idx < len(text) and (
                            text[end_idx].isspace() or text[end_idx].isdigit()
                        ):
                            end_idx += 1
                        break
                if end_idx > start_idx:
                    text = text[:start_idx] + text[end_idx:]
                else:
                    next_double_newline = text.find("\n\n", start_idx)
                    if next_double_newline != -1:
                        text = text[:start_idx] + text[next_double_newline:]
                    else:
                        text = text[:start_idx]
                    break
        return text
