"""Helpers for detecting figure labels and captions in PDF text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


_FIGURE_LINE_PATTERN = re.compile(
    r'^\s*(FIGURE\s+([A-Z0-9][\w\.\-()]*))(?:\s+(.+))?$', re.IGNORECASE
)
_CAPTION_STOP_PATTERN = re.compile(
    r'^(?:FIGURE|TABLE|CHAPTER|SECTION)\b', re.IGNORECASE
)
_SECTION_START_PATTERN = re.compile(r'^\d+(?:\.\d+)*\s+[A-Za-z]')


def _line_is_probably_caption(line: str) -> bool:
    """Heuristic to determine if a line belongs to a caption block."""
    stripped = line.strip()
    if not stripped:
        return False
    # Sentences that end in a period and aren't all uppercase are often prose
    if stripped.endswith(".") and not stripped.isupper():
        return False
    return True


@dataclass
class FigureLabel:
    """Metadata describing a figure identifier detected on a page."""

    number: str
    raw_label: str
    caption: Optional[str] = None

    @property
    def display_label(self) -> str:
        """Human-friendly label text with a fallback."""
        return self.raw_label or f"Figure {self.number}"


def extract_figure_labels(page_text: str, max_caption_lines: int = 2) -> list[FigureLabel]:
    """Detect figure labels within a block of page text.

    Args:
        page_text: Text extracted from a PDF page (after header/footer cleanup).
        max_caption_lines: Number of lines to treat as part of the caption
            following the FIGURE label line.

    Returns:
        List of FigureLabel instances discovered in reading order.
    """
    if not page_text:
        return []

    labels: list[FigureLabel] = []
    lines = page_text.splitlines()
    idx = 0

    while idx < len(lines):
        line = lines[idx].strip()
        match = _FIGURE_LINE_PATTERN.match(line)
        if match:
            raw_label = match.group(1).strip()
            figure_number = match.group(2).strip()
            remainder = (match.group(3) or "").strip()
            caption_lines: list[str] = []

            if remainder:
                caption_lines.append(remainder)

            cursor = idx + 1
            while cursor < len(lines) and len(caption_lines) < max_caption_lines:
                next_line = lines[cursor].strip()
                if not next_line:
                    break
                if (
                    _FIGURE_LINE_PATTERN.match(next_line)
                    or _CAPTION_STOP_PATTERN.match(next_line)
                    or _SECTION_START_PATTERN.match(next_line)
                ):
                    break
                if not _line_is_probably_caption(next_line):
                    break
                caption_lines.append(next_line)
                cursor += 1

            while caption_lines and not _line_is_probably_caption(caption_lines[-1]):
                caption_lines.pop()

            caption = " ".join(caption_lines).strip() or None
            labels.append(FigureLabel(number=figure_number, raw_label=raw_label, caption=caption))
            idx = cursor
            continue

        idx += 1

    return labels
