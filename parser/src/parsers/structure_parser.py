"""Structure parser for detecting document hierarchy."""

import logging
import re
from typing import Optional

from ..models import Chapter, Section, NumberedItem, Part
from ..utils.patterns import PATTERNS
from ..utils.formatters import extract_section_depth, clean_text


logger = logging.getLogger(__name__)


class StructureParser:
    """Parse PDF document structure into hierarchical format."""
    
    def __init__(self):
        """Initialize structure parser."""
        self.current_chapter: Optional[Chapter] = None
        self.current_part: Optional[Part] = None
        self.sections_stack: list[Section] = []
        self.user_notes_buffer: list[str] = []
        self.in_user_notes: bool = False
        
    def parse_text_to_structure(self, text: str, page_num: int) -> tuple[list[Chapter], list[Section]]:
        """Parse text content into chapters and sections.
        
        Args:
            text: Text content to parse
            page_num: Page number (1-indexed for display)
            
        Returns:
            Tuple of (chapters found, orphan sections)
        """
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
                title = self._extract_chapter_title(lines, line_idx)
                
                chapter = Chapter(chapter_number=chapter_num, title=title)
                chapters.append(chapter)
                self.current_chapter = chapter
                self.current_part = None
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
            if part_match:
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
                
                part = Part(part_number=part_num, title=part_title)
                if self.current_chapter:
                    self.current_chapter.parts.append(part)
                    self.current_part = part
                    # Clear sections stack when switching parts
                    self.sections_stack = []
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
                title = prefix_section_match.group(3).strip()
                
                section = self._create_section(section_num, title, prefix, page_num)
                current_section = section
                
                # Add to appropriate parent
                if self.current_chapter:
                    self._add_section_to_hierarchy(section, self.current_chapter)
                else:
                    orphan_sections.append(section)
                
                # Extract any remaining text after the title on the same line
                # The pattern captures up to and including the period, so we need to get text after it
                match_end = prefix_section_match.end()
                remaining_text = line[match_end:].strip()
                if remaining_text:
                    current_text_buffer.append(remaining_text)
                
                logger.debug(f"Found section [{prefix}] {section_num}: {title}")
                continue
            
            # Check for section without prefix
            section_match = PATTERNS['section'].match(line)
            if section_match and self._looks_like_section(line):
                # Save previous section
                if current_section and current_text_buffer:
                    current_section.text = ' '.join(current_text_buffer)
                    current_text_buffer = []
                
                section_num = section_match.group(1)
                title = section_match.group(2).strip()
                
                section = self._create_section(section_num, title, None, page_num)
                current_section = section
                
                # Add to appropriate parent
                if self.current_chapter:
                    self._add_section_to_hierarchy(section, self.current_chapter)
                else:
                    orphan_sections.append(section)
                
                # Extract any remaining text after the title on the same line
                match_end = section_match.end()
                remaining_text = line[match_end:].strip()
                if remaining_text:
                    current_text_buffer.append(remaining_text)
                
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
    
    def _extract_chapter_title(self, lines: list[str], current_idx: int) -> str:
        """Extract chapter title from following lines.
        
        Args:
            lines: All text lines
            current_idx: Current line index
            
        Returns:
            Chapter title
        """
        # Look at next few lines for title
        # Skip empty lines and look for the actual title (usually the next non-empty line)
        title_parts = []
        found_start = False
        
        for i in range(current_idx + 1, min(current_idx + 10, len(lines))):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                if found_start:
                    break  # Empty line after title, stop
                continue
            
            # Skip lines that are obviously not titles
            if (PATTERNS['chapter'].match(line) or 
                PATTERNS['user_notes'].match(line) or
                PATTERNS['part'].match(line) or
                PATTERNS['section_header'].match(line)):
                break
            
            # Check if this looks like a title (all caps, short, not a full sentence)
            if line.isupper() or (len(line.split()) <= 6 and not line.endswith('.')):
                title_parts.append(line)
                found_start = True
                
                # If this line has TOC dots/page numbers, we might have more on next line
                if '. . .' in line or re.search(r'\.\s+\.\s+\.', line):
                    continue  # Keep looking for continuation
                
                # If next line also looks like it could be a continuation, check it
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # Stop if next line is a PART or SECTION
                    if (PATTERNS['part'].match(next_line) or 
                        PATTERNS['section_header'].match(next_line)):
                        break
                    if next_line and (next_line.isupper() or '. . .' in next_line):
                        continue  # Keep looking
                
                # Otherwise, we have the complete title
                break
            elif found_start:
                # We were collecting title but this line doesn't match - stop
                break
        
        if title_parts:
            # Join all parts and clean
            full_title = ' '.join(title_parts)
            return clean_text(full_title)
        
        return "Untitled Chapter"
    
    def _looks_like_section(self, line: str) -> bool:
        """Heuristic to determine if a line is a section header.
        
        Args:
            line: Line to check
            
        Returns:
            True if likely a section header
        """
        # Section numbers are usually 2-4 digits, possibly with dots
        # And they're typically ALL CAPS or Title Case for titles
        parts = line.split(None, 1)
        if len(parts) < 2:
            return False
        
        section_num = parts[0]
        title = parts[1]
        
        # Section number should be numeric with optional dots
        if not re.match(r'^\d+(?:\.\d+)*$', section_num):
            return False
        
        # Title should be reasonably short (not a paragraph)
        if len(title) > 200:
            return False
        
        # Title often has uppercase words
        uppercase_words = sum(1 for word in title.split() if word.isupper() or word[0].isupper())
        if uppercase_words < len(title.split()) * 0.3:  # At least 30% capitalized
            return False
        
        return True
    
    def _create_section(
        self, 
        section_num: str, 
        title: str, 
        prefix: Optional[str],
        page_num: int
    ) -> Section:
        """Create a section object.
        
        Args:
            section_num: Section number
            title: Section title
            prefix: Section prefix ([A], [F], etc.)
            page_num: Page number
            
        Returns:
            Section object
        """
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
                page_number=str(page_num)
            ),
            references=References()
        )
        
        return section
    
    def _add_section_to_hierarchy(self, section: Section, chapter: Chapter) -> None:
        """Add section to appropriate place in hierarchy.
        
        Args:
            section: Section to add
            chapter: Current chapter
        """
        depth = section.depth
        
        # Determine where to add the section
        target_sections_list = None
        if self.current_part:
            # If we have a current part, add to part's sections
            target_sections_list = self.current_part.sections
        else:
            # Otherwise add to chapter's sections
            target_sections_list = chapter.sections
        
        if depth == 0:
            # Top-level section - add directly to target
            target_sections_list.append(section)
            self.sections_stack = [section]
        else:
            # Find parent section
            # Walk back through stack to find parent (depth - 1)
            parent_depth = depth - 1
            
            # Trim stack to parent level
            while len(self.sections_stack) > parent_depth + 1:
                self.sections_stack.pop()
            
            if self.sections_stack and len(self.sections_stack) > parent_depth:
                parent = self.sections_stack[parent_depth]
                parent.subsections.append(section)
                
                # Update stack
                if len(self.sections_stack) > depth:
                    self.sections_stack[depth] = section
                else:
                    self.sections_stack.append(section)
            else:
                # No valid parent found, add to target
                logger.warning(
                    f"Section {section.section_number} (depth {depth}) has no parent, "
                    f"adding to {'part' if self.current_part else 'chapter'}"
                )
                target_sections_list.append(section)
                self.sections_stack = [section]
    
    def parse_page_structure(
        self, 
        page_text: str, 
        page_num: int
    ) -> tuple[list[Chapter], list[Section]]:
        """Parse a single page for structure.
        
        Args:
            page_text: Text content of page
            page_num: Page number (1-indexed)
            
        Returns:
            Tuple of (chapters, sections) found on this page
        """
        return self.parse_text_to_structure(page_text, page_num)
    
    def merge_chapters(self, existing: list[Chapter], new: list[Chapter]) -> list[Chapter]:
        """Merge new chapters with existing ones.
        
        Args:
            existing: Existing chapter list
            new: New chapters to merge
            
        Returns:
            Merged chapter list
        """
        if not existing:
            return new
        
        result = list(existing)
        
        for new_chapter in new:
            # Check if chapter already exists
            found = False
            for existing_chapter in result:
                if existing_chapter.chapter_number == new_chapter.chapter_number:
                    # Update user notes if new chapter has them
                    if new_chapter.user_notes and not existing_chapter.user_notes:
                        existing_chapter.user_notes = new_chapter.user_notes
                    
                    # Merge parts
                    for new_part in new_chapter.parts:
                        # Check if part already exists
                        part_found = False
                        for existing_part in existing_chapter.parts:
                            if existing_part.part_number == new_part.part_number:
                                # Merge sections in part
                                existing_part.sections.extend(new_part.sections)
                                part_found = True
                                break
                        if not part_found:
                            existing_chapter.parts.append(new_part)
                    
                    # Merge standalone sections (not in parts)
                    existing_chapter.sections.extend(new_chapter.sections)
                    found = True
                    break
            
            if not found:
                result.append(new_chapter)
        
        return result
