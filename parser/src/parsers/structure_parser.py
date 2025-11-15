"""Structure parser for detecting document hierarchy."""

import logging
from typing import Optional

from ..models import Chapter, Section, NumberedItem
from ..utils.patterns import PATTERNS
from ..utils.formatters import extract_section_depth, clean_text
from .structure_utils import (
    align_line_features,
    compute_font_stats,
    extract_chapter_title,
    extract_title_and_inline_text,
    is_confident_part_heading,
    looks_like_section,
)


logger = logging.getLogger(__name__)


class StructureParser:
    """Parse PDF document structure into hierarchical format."""
    
    def __init__(self):
        """Initialize structure parser."""
        self.current_chapter: Optional[Chapter] = None
        self.user_notes_buffer: list[str] = []
        self.in_user_notes: bool = False
        self.last_section: Optional[Section] = None
        
    def parse_text_to_structure(
        self,
        text: str,
        page_num: int,
        *,
        lines: Optional[list[str]] = None,
        line_features: Optional[dict[int, dict]] = None,
        font_stats: Optional[dict[str, float]] = None,
    ) -> tuple[list[Chapter], list[Section]]:
        """Parse text content into chapters and sections.
        
        Args:
            text: Text content to parse
            page_num: Page number (1-indexed for display)
            
        Returns:
            Tuple of (chapters found, orphan sections)
        """
        if lines is None:
            lines = text.split('\n')
        chapters = []
        orphan_sections = []
        current_section = None
        current_text_buffer = []
        
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check for chapter header
            chapter_match = PATTERNS['chapter'].match(line)
            if chapter_match:
                # Save previous section
                if current_section and current_text_buffer:
                    current_section.text = ' '.join(current_text_buffer)
                    current_text_buffer = []
                
                # Save user notes if we were collecting them
                if self.in_user_notes and self.user_notes_buffer:
                    if self.current_chapter:
                        self.current_chapter.user_notes = ' '.join(self.user_notes_buffer)
                    self.user_notes_buffer = []
                    self.in_user_notes = False
                
                chapter_num = int(chapter_match.group(1))
                # Look ahead for chapter title (usually next non-empty line)
                title = extract_chapter_title(lines, line_idx)
                
                chapter = Chapter(chapter_number=chapter_num, title=title)
                chapters.append(chapter)
                self.current_chapter = chapter
                self.last_section = None
                current_section = None
                
                logger.info(f"Found chapter {chapter_num}: {title}")
                continue
            
            # Check for user notes
            user_notes_match = PATTERNS['user_notes'].match(line)
            if user_notes_match:
                self.in_user_notes = True
                self.user_notes_buffer = []
                continue
            
            # If we're in user notes section, collect lines until we hit a PART or SECTION header
            if self.in_user_notes:
                # Check if this line starts a new section
                if (PATTERNS['part'].match(line) or 
                    PATTERNS['section_header'].match(line) or
                    PATTERNS['prefix_section'].match(line)):
                    # End of user notes
                    if self.user_notes_buffer and self.current_chapter:
                        self.current_chapter.user_notes = ' '.join(self.user_notes_buffer)
                    self.user_notes_buffer = []
                    self.in_user_notes = False
                    # Don't continue - let the line be processed by other handlers
                else:
                    self.user_notes_buffer.append(line)
                    continue
            
            # Check for part header
            part_match = PATTERNS['part'].match(line)
            if part_match and is_confident_part_heading(line_idx, line_features, font_stats):
                # Save previous section
                if current_section and current_text_buffer:
                    current_section.text = ' '.join(current_text_buffer)
                    current_text_buffer = []
                
                part_num = int(part_match.group(1))
                part_title = clean_text(part_match.group(2))
                
                # Check if next line is a continuation of the part title (no SECTION/PART header)
                # This handles cases where part title spans multiple lines like:
                # "PART 2—ADMINISTRATION AND"
                # "ENFORCEMENT"
                if line_idx + 1 < len(lines):
                    next_line = lines[line_idx + 1].strip()
                    # If next line is all caps and doesn't start with SECTION/PART/[, it's likely a continuation
                    if (next_line and 
                        next_line.isupper() and 
                        not PATTERNS['section_header'].match(next_line) and
                        not PATTERNS['part'].match(next_line) and
                        not PATTERNS['prefix_section'].match(next_line) and
                        not PATTERNS['chapter'].match(next_line)):
                        part_title += ' ' + clean_text(next_line)
                        # Skip the next line since we've consumed it
                        lines[line_idx + 1] = ''  # Mark as processed
                
                if self.current_chapter:
                    logger.info(f"Found part {part_num}: {part_title}")
                current_section = None
                continue
            
            # Check for section header (e.g., "SECTION 101")
            section_header_match = PATTERNS['section_header'].match(line)
            if section_header_match:
                # This is just a header, the title usually comes next
                # We'll just log it and continue
                section_num = section_header_match.group(1)
                logger.debug(f"Found section header: SECTION {section_num}")
                continue
            
            # Check for section with prefix [A], [F], [BS], etc.
            prefix_section_match = PATTERNS['prefix_section'].match(line)
            if prefix_section_match:
                # Save previous section
                if current_section and current_text_buffer:
                    current_section.text = ' '.join(current_text_buffer)
                    current_text_buffer = []
                
                prefix = prefix_section_match.group(1)
                section_num = prefix_section_match.group(2)
                raw_title = prefix_section_match.group(3).strip()
                title, inline_text = extract_title_and_inline_text(raw_title)
                
                section = self._create_section(section_num, title, prefix, page_num)
                current_section = section
                
                # Add to appropriate parent
                if self.current_chapter:
                    self._add_section_to_hierarchy(section, self.current_chapter)
                else:
                    orphan_sections.append(section)
                
                if inline_text:
                    current_text_buffer.append(inline_text)
                
                logger.debug(f"Found section [{prefix}] {section_num}: {title}")
                continue
            
            # Check for section without prefix
            section_match = PATTERNS['section'].match(line)
            if section_match and looks_like_section(line):
                # Save previous section
                if current_section and current_text_buffer:
                    current_section.text = ' '.join(current_text_buffer)
                    current_text_buffer = []
                
                section_num = section_match.group(1)
                raw_title = section_match.group(2).strip()
                title, inline_text = extract_title_and_inline_text(raw_title)
                
                section = self._create_section(section_num, title, None, page_num)
                current_section = section
                
                # Add to appropriate parent
                if self.current_chapter:
                    self._add_section_to_hierarchy(section, self.current_chapter)
                else:
                    orphan_sections.append(section)
                
                if inline_text:
                    current_text_buffer.append(inline_text)
                
                logger.debug(f"Found section {section_num}: {title}")
                continue
            
            # Check for numbered items
            numbered_match = PATTERNS['numbered_item'].match(line)
            if numbered_match and current_section:
                item_num = int(numbered_match.group(1))
                item_text = numbered_match.group(2).strip()
                
                item = NumberedItem(number=item_num, text=item_text)
                current_section.numbered_items.append(item)
                
                logger.debug(f"Found numbered item {item_num} in section {current_section.section_number}")
                continue
            
            # Regular text - add to current section's text buffer
            if current_section:
                current_text_buffer.append(line)
        
        # Save final section
        if current_section and current_text_buffer:
            current_section.text = ' '.join(current_text_buffer)
        
        return chapters, orphan_sections

    def _create_section(
        self,
        section_num: str,
        title: str,
        prefix: Optional[str],
        page_num: int,
    ) -> Section:
        depth = extract_section_depth(section_num)
        from ..models import Metadata, References

        section = Section(
            section_number=section_num,
            prefix=prefix,
            title=title,
            depth=depth,
            metadata=Metadata(
                has_table=False,
                has_figure=False,
                table_count=0,
                figure_count=0,
                page_number=str(page_num),
            ),
            references=References(),
        )
        return section

    def _add_section_to_hierarchy(self, section: Section, chapter: Chapter) -> None:
        chapter.sections.append(section)
        self.last_section = section

    def parse_page_structure(
        self,
        page_text: str,
        page_num: int,
        line_features: Optional[list[dict]] = None
    ) -> tuple[list[Chapter], list[Section]]:
        """Parse a single page for structure."""
        lines = page_text.split('\n')
        font_lookup: Optional[dict[int, dict]] = None
        font_stats: Optional[dict[str, float]] = None
        if line_features:
            font_lookup = align_line_features(lines, line_features)
            font_stats = compute_font_stats(line_features)
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

        result = list(existing)
        for new_chapter in new:
            found = False
            for existing_chapter in result:
                if existing_chapter.chapter_number == new_chapter.chapter_number:
                    if new_chapter.user_notes and not existing_chapter.user_notes:
                        existing_chapter.user_notes = new_chapter.user_notes
                    existing_chapter.sections.extend(new_chapter.sections)
                    found = True
                    break
            if not found:
                result.append(new_chapter)
        return result
