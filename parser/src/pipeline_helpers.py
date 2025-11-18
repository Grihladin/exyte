"""Shared helpers for the document parsing pipeline."""

from __future__ import annotations

import logging
import re
from typing import Iterable

from src.models import Chapter, Section, TableData
from src.utils.tables import extract_table_labels


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

    label_texts = extract_table_labels(page_text)

    for idx, table_data in enumerate(tables):
        target_section = sections_on_page[min(idx, len(sections_on_page) - 1)]
        label = f"{page_num}.{idx + 1}"
        if idx < len(label_texts):
            full_label = label_texts[idx]
            label = re.sub(r"^.*?TABLE\s+", "", full_label, flags=re.IGNORECASE)

        table_key = _dedupe_key(label, document_tables)
        table_dict = {
            "page": table_data.page,
            "accuracy": table_data.accuracy,
        }
        if table_data.markdown:
            table_dict["markdown"] = table_data.markdown
        if table_data.image_path:
            table_dict["image_path"] = table_data.image_path
        if table_data.bbox:
            table_dict["bbox"] = list(table_data.bbox)
        if table_data.table_info:
            table_dict["table_info"] = table_data.table_info
        if table_data.table_name:
            table_dict["table_name"] = table_data.table_name
        document_tables[table_key] = table_dict

        if table_key not in target_section.references.table:
            target_section.references.table.append(table_key)

        if target_section.metadata:
            target_section.metadata.has_table = True
            target_section.metadata.table_count = len(target_section.references.table)

        accuracy_str = (
            f"{table_data.accuracy:.1f}%" if table_data.accuracy is not None else "n/a"
        )
        bbox_desc = table_data.bbox or "unknown bbox"
        image_desc = table_data.image_path or "no image"
        events_logger.info(
            "Page %d: Saved %s (accuracy: %s, image: %s, bbox: %s) -> Section %s",
            page_num,
            table_key,
            accuracy_str,
            image_desc,
            bbox_desc,
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
            target_section.metadata.figure_count = len(
                target_section.references.figures
            )

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
