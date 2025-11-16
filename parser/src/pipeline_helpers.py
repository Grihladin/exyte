"""Shared helpers for the document parsing pipeline."""

from __future__ import annotations

import logging
import re
from typing import Iterable

from src.models import Chapter, Section, TableData

_TABLE_HINT_PATTERN = re.compile(
    r"(?:^|\n)\s*TABLE\s+[A-Z0-9][\w\.\-()]*",
    re.IGNORECASE | re.MULTILINE,
)
_TABLE_LABEL_PATTERN = re.compile(
    r"(?:^|\n)\s*TABLE\s+[A-Z0-9][\w\.\-()]*",
    re.IGNORECASE | re.MULTILINE,
)
_FOOTER_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"COPYRIGHT.*?TABLE", re.IGNORECASE | re.DOTALL),
    re.compile(r"FEDERAL COPYRIGHT ACT.*?TABLE", re.IGNORECASE | re.DOTALL),
    re.compile(r"LICENSE AGREEMENT.*?TABLE", re.IGNORECASE | re.DOTALL),
)


def page_has_table_hint(page_text: str) -> bool:
    """Heuristic: detect obvious TABLE labels before invoking Camelot."""
    if not page_text:
        return False

    for footer_pattern in _FOOTER_PATTERNS:
        if footer_pattern.search(page_text):
            clean_text = footer_pattern.sub("", page_text)
            if not _TABLE_HINT_PATTERN.search(clean_text):
                return False

    return bool(_TABLE_HINT_PATTERN.search(page_text))


def attach_tables_to_sections(
    chapters: list[Chapter],
    tables: list[TableData],
    page_num: int,
    page_text: str,
    fallback_section: Section | None,
    document_tables: dict[str, dict] | None,
    events_logger: logging.Logger,
) -> None:
    """Store extracted tables and hook them up to the appropriate section."""
    if document_tables is None:
        document_tables = {}

    sections_on_page = [section for chapter in chapters for section in chapter.sections]
    if not sections_on_page and fallback_section is not None:
        sections_on_page = [fallback_section]
    if not sections_on_page:
        events_logger.warning(
            "Page %d: Found %d table(s) but no sections to attach to",
            page_num,
            len(tables),
        )
        return

    page_text_clean = page_text or ""
    for footer_pattern in _FOOTER_PATTERNS:
        page_text_clean = footer_pattern.sub("", page_text_clean)
    label_matches = list(_TABLE_LABEL_PATTERN.finditer(page_text_clean))

    for idx, table_data in enumerate(tables):
        target_section = sections_on_page[min(idx, len(sections_on_page) - 1)]
        label = f"{page_num}.{idx + 1}"
        if idx < len(label_matches):
            match = label_matches[idx]
            full_label = match.group(0).strip()
            label = re.sub(r"^.*?TABLE\s+", "", full_label, flags=re.IGNORECASE)

        table_key = _dedupe_key(label, document_tables)
        table_dict = {
            "headers": table_data.headers,
            "rows": table_data.rows,
            "page": table_data.page,
            "accuracy": table_data.accuracy,
        }
        document_tables[table_key] = table_dict

        if table_key not in target_section.references.table:
            target_section.references.table.append(table_key)

        if target_section.metadata:
            target_section.metadata.has_table = True
            target_section.metadata.table_count = len(target_section.references.table)

        events_logger.info(
            "Page %d: Extracted %s (accuracy: %.1f%%, %d cols × %d rows) -> Section %s",
            page_num,
            table_key,
            table_data.accuracy or 0,
            len(table_data.headers),
            len(table_data.rows),
            target_section.section_number,
        )


def attach_figures_to_sections(
    chapters: list[Chapter],
    figures: Iterable[dict],
    page_num: int,
    fallback_section: Section | None,
    document_figures: dict[str, dict] | None,
    events_logger: logging.Logger,
) -> None:
    """Store figure metadata at the document root and link it to sections."""
    figures = list(figures)

    if document_figures is None:
        document_figures = {}

    sections_on_page = [section for chapter in chapters for section in chapter.sections]
    if not sections_on_page and fallback_section is not None:
        sections_on_page = [fallback_section]
    if not sections_on_page:
        events_logger.warning(
            "Page %d: Found %d figure(s) but no sections to attach to",
            page_num,
            len(figures),
        )
        return

    for idx, figure_data in enumerate(figures):
        target_section = sections_on_page[min(idx, len(sections_on_page) - 1)]
        figure_id = figure_data["figure_id"]

        document_figures[figure_id] = figure_data

        if figure_id not in target_section.references.figures:
            target_section.references.figures.append(figure_id)

        if target_section.metadata:
            target_section.metadata.has_figure = True
            target_section.metadata.figure_count = len(target_section.references.figures)

        label = figure_data.get("label") or figure_data.get("figure_number")
        figure_desc = f"{figure_id} ({label})" if label else figure_id

        events_logger.info(
            "Page %d: Extracted %s (%dx%d %s) -> Section %s",
            page_num,
            figure_desc,
            figure_data.get("width", 0),
            figure_data.get("height", 0),
            figure_data.get("format", "unknown"),
            target_section.section_number,
        )


def _dedupe_key(base_label: str, storage: dict[str, dict]) -> str:
    """Ensure generated keys do not collide with existing entries."""
    table_key = base_label
    suffix = 1
    while table_key in storage:
        table_key = f"{base_label}_{suffix}"
        suffix += 1
    return table_key
