"""Core parsing/extraction pipeline helpers."""

from __future__ import annotations

import logging
from pathlib import Path

from src.config import JSON_OUTPUT_FILE, OUTPUT_DIR, IMAGES_DIR
from src.models import Chapter, Document, Section, TableData
from src.parsers import (
    MetadataCollector,
    PDFExtractor,
    ReferenceExtractor,
    StructureParser,
    TableExtractor,
)
from src.parsers.figure_extractor import FigureExtractor
from src.pipeline_helpers import (
    attach_figures_to_sections,
    attach_tables_to_sections,
    page_has_table_hint,
)
from src.utils.figures import extract_figure_labels
from .pipeline_pdf import run_pdf_phase
from tqdm.auto import tqdm

EVENT_LOG_FILE = OUTPUT_DIR / "events.log"
_events_logger = logging.getLogger("parser.events")
if not _events_logger.handlers:
    handler = logging.FileHandler(EVENT_LOG_FILE, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    _events_logger.addHandler(handler)
_events_logger.setLevel(logging.INFO)


def run_structure_phase(pdf_path: str | Path, num_pages: int, start_page: int) -> None:
    """Parse document structure with progress bar and event logging."""
    structure_parser = StructureParser()
    reference_extractor = ReferenceExtractor()
    metadata_collector = MetadataCollector()
    table_extractor = TableExtractor(pdf_path)

    # Document-level tables and figures storage
    document_tables: dict[str, dict] = {}
    document_figures: dict[str, dict] = {}

    with PDFExtractor(pdf_path) as extractor:
        figure_extractor = FigureExtractor(extractor, IMAGES_DIR)
        
        total_pages = extractor.get_page_count()
        if start_page >= total_pages:
            raise ValueError(
                f"Start page ({start_page + 1}) is beyond total pages ({total_pages})."
            )

        pages_to_parse = min(num_pages, total_pages - start_page)
        all_chapters: list[Chapter] = []
        all_orphan_sections = []

        with tqdm(total=pages_to_parse, desc="Parsing pages", unit="page") as progress:
            for page_offset in range(pages_to_parse):
                page_num = start_page + page_offset
                text = extractor.extract_page_text(page_num)
                line_features = extractor.extract_page_lines_with_fonts(page_num)
                chapters, orphan_sections = structure_parser.parse_page_structure(
                    text,
                    page_num + 1,
                    line_features=line_features,
                )

                if chapters:
                    for chapter in chapters:
                        _events_logger.info(
                            "Page %d: Detected Chapter %s - %s",
                            page_num + 1,
                            chapter.chapter_number,
                            chapter.title,
                        )

                tables: list[TableData] = []
                if page_has_table_hint(text):
                    _events_logger.debug("Page %d: Table hint detected, attempting extraction", page_num + 1)
                    tables = table_extractor.extract_tables(page_num + 1)
                    if not tables:
                        _events_logger.warning(
                            "Page %d: Table hint detected but extraction failed (check table format)",
                            page_num + 1,
                        )
                    else:
                        _events_logger.debug(
                            "Page %d: Successfully extracted %d table(s)",
                            page_num + 1,
                            len(tables)
                        )
                if tables:
                    attach_tables_to_sections(
                        chapters,
                        tables,
                        page_num + 1,
                        text,
                        structure_parser.last_section,
                        document_tables,
                        _events_logger,
                    )
                
                # Extract figures from page with detected labels/captions
                figure_labels = extract_figure_labels(text)
                figures = figure_extractor.extract_figures_from_page(
                    page_num,
                    str(page_num + 1),
                    figure_labels=figure_labels,
                )
                if figures:
                    attach_figures_to_sections(
                        chapters,
                        figures,
                        page_num + 1,
                        structure_parser.last_section,
                        document_figures,
                        _events_logger,
                    )

                all_chapters = structure_parser.merge_chapters(all_chapters, chapters)
                if structure_parser.current_chapter:
                    for ch in all_chapters:
                        if ch.chapter_number == structure_parser.current_chapter.chapter_number:
                            structure_parser.current_chapter = ch
                            break

                all_orphan_sections.extend(orphan_sections)
                progress.update(1)

    cleaned_chapters = []
    seen_chapters = {}
    for chapter in all_chapters:
        chapter_key = chapter.chapter_number
        has_content = bool(chapter.sections or chapter.user_notes)
        if chapter_key in seen_chapters:
            existing = seen_chapters[chapter_key]
            if has_content:
                if not (existing.sections or existing.user_notes):
                    seen_chapters[chapter_key] = chapter
                else:
                    if chapter.user_notes and not existing.user_notes:
                        existing.user_notes = chapter.user_notes
                    existing.sections.extend(chapter.sections)
        else:
            if has_content:
                seen_chapters[chapter_key] = chapter
                cleaned_chapters.append(chapter)

    all_chapters = cleaned_chapters
    for chapter in all_chapters:
        for section in chapter.sections:
            reference_extractor.extract_and_attach_references(section)
            metadata_collector.collect_section_metadata(section)

    from src.config import DOCUMENT_TITLE, DOCUMENT_VERSION

    document = Document(
        title=DOCUMENT_TITLE,
        version=DOCUMENT_VERSION,
        chapters=all_chapters,
        tables=document_tables,
        figures=document_figures,
    )
    json_output = document.model_dump_json(indent=2)
    JSON_OUTPUT_FILE.write_text(json_output)
