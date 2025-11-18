"""Utilities for detecting table hints and labels in PDF text."""

from __future__ import annotations

import re

# Regex patterns reused by pipeline helpers and table extraction
# Updated to support optional prefixes like [F], [A], [BS], etc.
_TABLE_HINT_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:\[[A-Z]+\]\s+)?TABLE\s+[A-Z0-9][\w\.\-()]*",
    re.IGNORECASE | re.MULTILINE,
)
_TABLE_LABEL_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:\[[A-Z]+\]\s+)?TABLE\s+[A-Z0-9][\w\.\-()]*",
    re.IGNORECASE | re.MULTILINE,
)
_FOOTER_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"COPYRIGHT.*?TABLE", re.IGNORECASE | re.DOTALL),
    re.compile(r"FEDERAL COPYRIGHT ACT.*?TABLE", re.IGNORECASE | re.DOTALL),
    re.compile(r"LICENSE AGREEMENT.*?TABLE", re.IGNORECASE | re.DOTALL),
)


def _strip_table_footers(page_text: str | None) -> str:
    """Remove known footer noise prior to regex searches."""
    cleaned = page_text or ""
    for footer_pattern in _FOOTER_PATTERNS:
        cleaned = footer_pattern.sub("", cleaned)
    return cleaned


def page_has_table_hint(page_text: str | None) -> bool:
    """Heuristic: detect obvious TABLE labels before heavier processing."""
    if not page_text:
        return False
    cleaned = _strip_table_footers(page_text)
    return bool(_TABLE_HINT_PATTERN.search(cleaned))


def extract_table_labels(page_text: str | None) -> list[str]:
    """Return ordered TABLE labels detected within page text."""
    if not page_text:
        return []
    cleaned = _strip_table_footers(page_text)
    return [match.group(0).strip() for match in _TABLE_LABEL_PATTERN.finditer(cleaned)]
