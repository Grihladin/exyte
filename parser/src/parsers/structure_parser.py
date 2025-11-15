"""Structure parser for detecting document hierarchy."""

import logging
import re
import statistics
from typing import Optional

from ..models import Chapter, Section, NumberedItem
from ..utils.patterns import PATTERNS
from ..utils.formatters import extract_section_depth, clean_text


logger = logging.getLogger(__name__)


class StructureParser:
    """Parse PDF document structure into hierarchical format."""
    
    def __init__(self):
        """Initialize structure parser."""
        self.current_chapter: Optional[Chapter] = None
        self.user_notes_buffer: list[str] = []
        self.in_user_notes: bool = False
        
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
                title = self._extract_chapter_title(lines, line_idx)
                
                chapter = Chapter(chapter_number=chapter_num, title=title)
                chapters.append(chapter)
                self.current_chapter = chapter
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
            if part_match and self._is_confident_part_heading(line_idx, line_features, font_stats):
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
                title, inline_text = self._extract_title_and_inline_text(raw_title)
                
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
            if section_match and self._looks_like_section(line):
                # Save previous section
                if current_section and current_text_buffer:
                    current_section.text = ' '.join(current_text_buffer)
                    current_text_buffer = []
                
                section_num = section_match.group(1)
                raw_title = section_match.group(2).strip()
                title, inline_text = self._extract_title_and_inline_text(raw_title)
                
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
        
        # Require the first significant token to look like a heading (start with uppercase letter)
        first_token = title.split()[0] if title.split() else ""
        first_token = first_token.lstrip('(["')
        if not first_token or not first_token[0].isupper():
            return False
        
        # Title often has uppercase words
        uppercase_words = sum(1 for word in title.split() if word.isupper() or word[0].isupper())
        if uppercase_words < len(title.split()) * 0.3:  # At least 30% capitalized
            return False
        
        return True
    
    def _extract_title_and_inline_text(self, text: str) -> tuple[str, str]:
        """Split section line into title and inline body text."""
        normalized = text.strip()
        if not normalized:
            return "", ""
        split_match = re.search(r'\.\s+(?=[A-Z\[])', normalized)
        if split_match:
            title = normalized[:split_match.start()].strip()
            inline_text = normalized[split_match.end():].strip()
            return clean_text(title.rstrip('.')), inline_text
        return clean_text(normalized.rstrip('.')), ""
    
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
        chapter.sections.append(section)

    def _normalize_line_text(self, text: str) -> str:
        """Normalize line text for comparisons."""
        return re.sub(r'\s+', ' ', text.strip())

    def _align_line_features(self, lines: list[str], features: list[dict]) -> dict[int, dict]:
        """Align extracted line features with filtered text lines."""
        lookup: dict[int, dict] = {}
        feature_idx = 0
        total_features = len(features)
        for line_idx, line in enumerate(lines):
            normalized_line = self._normalize_line_text(line)
            if not normalized_line:
                continue
            while feature_idx < total_features:
                feature = features[feature_idx]
                feature_idx += 1
                normalized_feature = self._normalize_line_text(feature.get('text', ''))
                if not normalized_feature:
                    continue
                if normalized_feature == normalized_line:
                    lookup[line_idx] = feature
                    break
        return lookup

    def _compute_font_stats(self, features: list[dict]) -> dict[str, float]:
        """Compute basic statistics about font sizes on a page."""
        sizes = [feature.get('max_size') for feature in features if feature.get('max_size')]
        if not sizes:
            return {}
        median_size = statistics.median(sizes)
        avg_size = sum(sizes) / len(sizes)
        max_size = max(sizes)
        return {
            'median': float(median_size),
            'average': float(avg_size),
            'max': float(max_size),
        }

    def _is_confident_part_heading(
        self,
        line_idx: int,
        line_features: Optional[dict[int, dict]],
        font_stats: Optional[dict[str, float]],
    ) -> bool:
        """Determine if a PART line is likely a heading using font cues when available."""
        if not line_features or line_idx not in line_features:
            return True
        info = line_features[line_idx]
        font_size = info.get('max_size') or info.get('size')
        if font_size is None:
            return True
        median_size = (font_stats or {}).get('median', 0.0)
        max_size = (font_stats or {}).get('max', 0.0)
        # Treat as heading if noticeably larger or bold compared to body text
        if font_size >= max(12.0, median_size + 1.0):
            return True
        if max_size and font_size >= max_size * 0.9:
            return True
        if info.get('is_bold') and font_size >= median_size:
            return True
        return False

    def parse_page_structure(
        self, 
        page_text: str, 
        page_num: int,
        line_features: Optional[list[dict]] = None
    ) -> tuple[list[Chapter], list[Section]]:
        """Parse a single page for structure.
        
        Args:
            page_text: Text content of page
            page_num: Page number (1-indexed)
            line_features: Optional line appearance information per line
            
        Returns:
            Tuple of (chapters, sections) found on this page
        """
        lines = page_text.split('\n')
        font_lookup: Optional[dict[int, dict]] = None
        font_stats: Optional[dict[str, float]] = None
        if line_features:
            font_lookup = self._align_line_features(lines, line_features)
            font_stats = self._compute_font_stats(line_features)
        return self.parse_text_to_structure(
            page_text,
            page_num,
            lines=lines,
            line_features=font_lookup,
            font_stats=font_stats,
        )
    
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
                    
                    # Merge standalone sections (not in parts)
                    existing_chapter.sections.extend(new_chapter.sections)
                    found = True
                    break
            
            if not found:
                result.append(new_chapter)
        
        return result
