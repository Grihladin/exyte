"""Core parsing/extraction pipeline helpers."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from src.config import (
    JSON_OUTPUT_FILE,
    OUTPUT_DIR,
)
from src.parsers import (
    PDFExtractor,
    StructureParser,
    ReferenceExtractor,
    MetadataCollector,
    TableExtractor,
)
from src.models import Document, TableReference, Position, TableData, Chapter, Section
from .pipeline_pdf import run_pdf_phase
from tqdm.auto import tqdm

EVENT_LOG_FILE = OUTPUT_DIR / "events.log"
_events_logger = logging.getLogger("parser.events")
if not _events_logger.handlers:
    handler = logging.FileHandler(EVENT_LOG_FILE, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    _events_logger.addHandler(handler)
_events_logger.setLevel(logging.INFO)


_TABLE_HINT_PATTERN = re.compile(r"\bTABLE\s+[A-Z0-9]", re.IGNORECASE)
_TABLE_LABEL_PATTERN = re.compile(r"\bTABLE\s+[A-Z0-9][\w\.\-()]*", re.IGNORECASE)



def _attach_tables_to_sections(
    chapters: list[Chapter],
    tables: list[TableData],
    page_num: int,
    page_text: str,
    fallback_section: Section | None = None,
) -> None:
    """Attach Camelot tables to the best available section on the page."""
    sections_on_page = [section for chapter in chapters for section in chapter.sections]
    if not sections_on_page and fallback_section is not None:
        sections_on_page = [fallback_section]
    if not sections_on_page:
        return
    label_matches = list(_TABLE_LABEL_PATTERN.finditer(page_text or ""))
    for idx, table_data in enumerate(tables):
        target_section = sections_on_page[min(idx, len(sections_on_page) - 1)]
        label = f"Page {page_num} Table {idx + 1}"
        position = Position(start=0, end=0)
        if idx < len(label_matches):
            match = label_matches[idx]
            label = match.group(0).strip()
            position = Position(start=match.start(), end=match.end())
        table_ref = TableReference(
            reference=label,
            position=position,
            table_data=table_data,
        )
        target_section.references.tables.append(table_ref)
        if target_section.metadata:
            target_section.metadata.has_table = True
            target_section.metadata.table_count = len(target_section.references.tables)
        _events_logger.info(
            "Page %d: Attached %s to Section %s",
            page_num,
            label,
            target_section.section_number,
        )


def _page_has_table_hint(page_text: str) -> bool:
    """Heuristic: detect obvious TABLE labels before invoking Camelot."""
    if not page_text:
        return False
    return bool(_TABLE_HINT_PATTERN.search(page_text))


def _log_progress(current: int, total: int) -> None:
    if total <= 0:
        return
    current = min(current, total)
    fraction = current / total
    bar_len = 30
    filled = int(bar_len * fraction)
    bar = "█" * filled + "-" * (bar_len - filled)
    message = f"[{bar}] {current}/{total} pages ({fraction * 100:.1f}%)"
    sys.stdout.write("\r" + message)
    sys.stdout.flush()
    if current == total:
        sys.stdout.write("\n")


def run_structure_phase(pdf_path: str | Path, num_pages: int, start_page: int) -> None:
    """Parse document structure with progress bar and event logging."""
    structure_parser = StructureParser()
    reference_extractor = ReferenceExtractor()
    metadata_collector = MetadataCollector()
    table_extractor = TableExtractor(pdf_path)

    with PDFExtractor(pdf_path) as extractor:
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
                if _page_has_table_hint(text):
                    _events_logger.info("Page %d: Table hint detected", page_num + 1)
                    tables = table_extractor.extract_tables(page_num + 1)
                    if not tables:
                        _events_logger.info(
                            "Page %d: Table hint but no tables extracted",
                            page_num + 1,
                        )
                if tables:
                    _attach_tables_to_sections(
                        chapters,
                        tables,
                        page_num + 1,
                        text,
                        structure_parser.last_section,
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
    )
    json_output = document.model_dump_json(indent=2)
    JSON_OUTPUT_FILE.write_text(json_output)
