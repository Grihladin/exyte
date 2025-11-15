"""Quick test to verify sections are flattened without part metadata."""

import sys
import logging
from pathlib import Path

# Change to parser directory for proper imports
import os
os.chdir(Path(__file__).parent / "parser")
sys.path.insert(0, str(Path.cwd()))

from src.parsers import PDFExtractor, StructureParser
from src.models import Section

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def test_part_parsing():
    """Test that sections are parsed without part metadata or subsections."""
    pdf_path = "../2021_International_Building_Code.pdf"
    
    logger.info("Testing PART header parsing...")
    logger.info("=" * 80)
    
    with PDFExtractor(pdf_path) as extractor:
        structure_parser = StructureParser()
        
        start_page = 31  # zero-based index for page 32
        pages_to_parse = 2
        all_chapters = []
        for page_num in range(start_page, start_page + pages_to_parse):
            text = extractor.extract_page_text(page_num)
            line_features = extractor.extract_page_lines_with_fonts(page_num)
            chapters, _ = structure_parser.parse_page_structure(
                text,
                page_num + 1,
                line_features=line_features,
            )
            all_chapters = structure_parser.merge_chapters(all_chapters, chapters)
            
            # Update references
            if structure_parser.current_chapter:
                for ch in all_chapters:
                    if ch.chapter_number == structure_parser.current_chapter.chapter_number:
                        structure_parser.current_chapter = ch
                        break
        
        # Check results
        logger.info("\n" + "=" * 80)
        logger.info("RESULTS:")
        logger.info("=" * 80)
        
        total_sections = sum(len(ch.sections) for ch in all_chapters)
        assert total_sections > 0, "No sections parsed from sample pages"

        # Validate model schema does not expose part/subsection fields
        for field in ("part_number", "part_title", "subsections"):
            assert field not in Section.model_fields, f"Field '{field}' should not exist on Section"

        for chapter in all_chapters:
            logger.info(f"\nChapter {chapter.chapter_number}: {chapter.title}")
            logger.info(f"  Sections detected: {len(chapter.sections)}")
            for section in chapter.sections[:5]:
                logger.info(
                    f"    Section {section.section_number}: {section.title}"
                )


if __name__ == "__main__":
    test_part_parsing()
