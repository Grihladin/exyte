"""Structure parser for detecting document hierarchy."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Sequence

from ..models import Chapter, Section, NumberedItem, Metadata, References
from ..utils.formatters import clean_text, extract_section_depth
from ..utils.patterns import PATTERNS
from .structure_utils import (
    align_line_features,
    compute_font_stats,
    extract_chapter_title,
    extract_title_and_inline_text,
    is_confident_part_heading,
    looks_like_section,
)

logger = logging.getLogger(__name__)


@dataclass
class _SectionState:
    """Tracks mutable parsing state for a page."""

    chapters: list[Chapter] = field(default_factory=list)
    orphan_sections: list[Section] = field(default_factory=list)
    current_section: Optional[Section] = None
    text_buffer: list[str] = field(default_factory=list)

    def flush_current_section(self) -> None:
        if self.current_section and self.text_buffer:
            self.current_section.text = " ".join(self.text_buffer)
            self.text_buffer.clear()

class StructureParser:
    """Parse PDF document structure into hierarchical format."""

    def __init__(self) -> None:
        self.current_chapter: Optional[Chapter] = None
        self.user_notes_buffer: list[str] = []
        self.in_user_notes = False
        self.last_section: Optional[Section] = None

    # Public API ----------------------------------------------------
    def parse_text_to_structure(
        self,
        text: str,
        page_num: int,
        *,
        lines: Optional[Sequence[str]] = None,
        line_features: Optional[dict[int, dict]] = None,
        font_stats: Optional[dict[str, float]] = None,
    ) -> tuple[list[Chapter], list[Section]]:
        """Parse text content into chapters and sections."""
        source_lines = list(lines) if lines is not None else text.splitlines()
        state = _SectionState()

        for line_idx, raw_line in enumerate(source_lines):
            line = raw_line.strip()
            if not line:
                continue

            if self._handle_chapter_line(line, line_idx, source_lines, state):
                continue
            if self._handle_user_notes_line(line):
                continue
            if self._handle_part_line(
                line,
                line_idx,
                source_lines,
                state,
                line_features,
                font_stats,
            ):
                continue
            section_header = PATTERNS["section_header"].match(line)
            if section_header:
                logger.debug("Found section header: SECTION %s", section_header.group(1))
                continue
            prefix_match = PATTERNS["prefix_section"].match(line)
            if prefix_match and self._start_section(
                prefix_match.group(2),
                prefix_match.group(1),
                prefix_match.group(3).strip(),
                page_num,
                state,
            ):
                continue
            section_match = PATTERNS["section"].match(line)
            if section_match and looks_like_section(line) and self._start_section(
                section_match.group(1),
                None,
                section_match.group(2).strip(),
                page_num,
                state,
            ):
                continue
            numbered_match = PATTERNS["numbered_item"].match(line)
            if numbered_match and state.current_section:
                item = NumberedItem(
                    number=int(numbered_match.group(1)),
                    text=numbered_match.group(2).strip(),
                )
                state.current_section.numbered_items.append(item)
                logger.debug("Found numbered item %s in section %s", item.number, state.current_section.section_number)
                continue
            if state.current_section:
                state.text_buffer.append(line)

        state.flush_current_section()
        return state.chapters, state.orphan_sections

    def parse_page_structure(
        self,
        page_text: str,
        page_num: int,
        line_features: Optional[list[dict]] = None,
    ) -> tuple[list[Chapter], list[Section]]:
        """Parse a single page for chapters/sections."""
        lines = page_text.splitlines()
        font_lookup = align_line_features(lines, line_features) if line_features else None
        font_stats = compute_font_stats(line_features) if line_features else None
        return self.parse_text_to_structure(
            page_text,
            page_num,
            lines=lines,
            line_features=font_lookup,
            font_stats=font_stats,
        )

    def merge_chapters(self, existing: list[Chapter], new: list[Chapter]) -> list[Chapter]:
        if not existing:
            return new

        merged = list(existing)
        for candidate in new:
            match = next(
                (chapter for chapter in merged if chapter.chapter_number == candidate.chapter_number),
                None,
            )
            if match:
                if candidate.user_notes and not match.user_notes:
                    match.user_notes = candidate.user_notes
                match.sections.extend(candidate.sections)
            else:
                merged.append(candidate)
        return merged

    # Line handlers -------------------------------------------------
    def _handle_chapter_line(
        self,
        line: str,
        line_idx: int,
        lines: list[str],
        state: _SectionState,
    ) -> bool:
        match = PATTERNS["chapter"].match(line)
        if not match:
            return False

        state.flush_current_section()
        self._finalize_user_notes()

        chapter_num = int(match.group(1))
        title = extract_chapter_title(lines, line_idx)
        chapter = Chapter(chapter_number=chapter_num, title=title)

        state.chapters.append(chapter)
        self.current_chapter = chapter
        self.last_section = None

        logger.info("Found chapter %s: %s", chapter_num, title)
        return True

    def _handle_user_notes_line(self, line: str) -> bool:
        if PATTERNS["user_notes"].match(line):
            self.in_user_notes = True
            self.user_notes_buffer = []
            return True

        if not self.in_user_notes:
            return False

        if self._line_starts_new_section(line):
            self._finalize_user_notes()
            return False

        self.user_notes_buffer.append(line)
        return True

    def _handle_part_line(
        self,
        line: str,
        line_idx: int,
        lines: list[str],
        state: _SectionState,
        line_features: Optional[dict[int, dict]],
        font_stats: Optional[dict[str, float]],
    ) -> bool:
        match = PATTERNS["part"].match(line)
        if not match or not is_confident_part_heading(line_idx, line_features, font_stats):
            return False

        state.flush_current_section()
        part_num = int(match.group(1))
        part_title = self._maybe_extend_part_title(clean_text(match.group(2)), line_idx, lines)
        if self.current_chapter:
            logger.info("Found part %s: %s", part_num, part_title)
        state.current_section = None
        return True

    # Helpers -------------------------------------------------------
    def _start_section(
        self,
        section_num: str,
        prefix: Optional[str],
        raw_title: str,
        page_num: int,
        state: _SectionState,
    ) -> bool:
        state.flush_current_section()

        title, inline_text = extract_title_and_inline_text(raw_title)
        section = self._create_section(section_num, title, prefix, page_num)

        if self.current_chapter:
            self._add_section_to_hierarchy(section, self.current_chapter)
        else:
            state.orphan_sections.append(section)
            self.last_section = section

        state.current_section = section
        if inline_text:
            state.text_buffer.append(inline_text)

        logger.debug("Found section %s%s: %s", f"[{prefix}] " if prefix else "", section_num, title)
        return True

    def _create_section(
        self,
        section_num: str,
        title: str,
        prefix: Optional[str],
        page_num: int,
    ) -> Section:
        depth = extract_section_depth(section_num)
        metadata = Metadata(
            has_table=False,
            has_figure=False,
            table_count=0,
            figure_count=0,
            page_number=str(page_num),
        )
        return Section(
            section_number=section_num,
            prefix=prefix,
            title=title,
            depth=depth,
            metadata=metadata,
            references=References(),
        )

    def _add_section_to_hierarchy(self, section: Section, chapter: Chapter) -> None:
        chapter.sections.append(section)
        self.last_section = section

    def _finalize_user_notes(self) -> None:
        if self.in_user_notes and self.user_notes_buffer and self.current_chapter:
            self.current_chapter.user_notes = " ".join(self.user_notes_buffer)
        self.in_user_notes = False
        self.user_notes_buffer = []

    @staticmethod
    def _line_starts_new_section(line: str) -> bool:
        patterns = (
            PATTERNS["part"],
            PATTERNS["section_header"],
            PATTERNS["prefix_section"],
            PATTERNS["section"],
            PATTERNS["chapter"],
        )
        return any(pattern.match(line) for pattern in patterns)

    @staticmethod
    def _maybe_extend_part_title(title: str, line_idx: int, lines: list[str]) -> str:
        if line_idx + 1 >= len(lines):
            return title

        next_line = lines[line_idx + 1].strip()
        if (
            next_line
            and next_line.isupper()
            and not StructureParser._line_starts_new_section(next_line)
        ):
            lines[line_idx + 1] = ""
            return f"{title} {clean_text(next_line)}"
        return title
