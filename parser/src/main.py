"""Main entry point for PDF parser - Phase 2: Structure Parsing."""

import logging
import sys
from pathlib import Path

from src.config import LOG_LEVEL, LOG_FORMAT, JSON_OUTPUT_FILE
from src.parsers import PDFExtractor, StructureParser, ReferenceExtractor, MetadataCollector
from src.models import Document


# Set up logging
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def test_structure_parsing(pdf_path: str, num_pages: int = 10) -> None:
    """Test PDF structure parsing on sample pages.
    
    Args:
        pdf_path: Path to PDF file
        num_pages: Number of pages to parse (default: 10)
    """
    logger.info("=" * 80)
    logger.info("Phase 2: Structure Parsing Testing")
    logger.info("=" * 80)
    
    try:
        # Initialize parsers
        structure_parser = StructureParser()
        reference_extractor = ReferenceExtractor()
        metadata_collector = MetadataCollector()
        
        # Initialize PDF extractor
        with PDFExtractor(pdf_path) as extractor:
            total_pages = extractor.get_page_count()
            logger.info(f"PDF loaded successfully: {total_pages} pages")
            
            # Limit to available pages
            pages_to_parse = min(num_pages, total_pages)
            logger.info(f"Parsing first {pages_to_parse} pages for structure...")
            
            all_chapters = []
            all_orphan_sections = []
            
            # Parse pages for structure
            for page_num in range(pages_to_parse):
                logger.info(f"\n--- Processing Page {page_num + 1} ---")
                
                # Extract text
                text = extractor.extract_page_text(page_num)
                
                # Parse structure
                chapters, orphan_sections = structure_parser.parse_page_structure(text, page_num + 1)
                
                if chapters:
                    logger.info(f"Found {len(chapters)} chapter(s)")
                    for chapter in chapters:
                        logger.info(f"  Chapter {chapter.chapter_number}: {chapter.title}")
                        logger.info(f"    {len(chapter.sections)} section(s)")
                
                if orphan_sections:
                    logger.info(f"Found {len(orphan_sections)} orphan section(s)")
                
                # Merge chapters
                all_chapters = structure_parser.merge_chapters(all_chapters, chapters)
                
                # Update parser's current_chapter to point to the merged chapter in all_chapters
                # This ensures subsequent pages add to the correct chapter object
                if structure_parser.current_chapter:
                    for ch in all_chapters:
                        if ch.chapter_number == structure_parser.current_chapter.chapter_number:
                            structure_parser.current_chapter = ch
                            # Also update current_part reference
                            if structure_parser.current_part:
                                for part in ch.parts:
                                    if part.part_number == structure_parser.current_part.part_number:
                                        structure_parser.current_part = part
                                        break
                            break
                
                all_orphan_sections.extend(orphan_sections)
            
            logger.info("\n" + "=" * 80)
            logger.info("Structure Parsing Summary")
            logger.info("=" * 80)
            
            # Clean up chapters: remove duplicates and empty chapters from TOC
            logger.info("\nCleaning up duplicate and empty chapters...")
            cleaned_chapters = []
            seen_chapters = {}
            
            for chapter in all_chapters:
                chapter_key = chapter.chapter_number
                
                # Check if this chapter has actual content
                has_content = (
                    bool(chapter.sections) or 
                    bool(chapter.parts) or 
                    bool(chapter.user_notes)
                )
                
                if chapter_key in seen_chapters:
                    # Chapter already exists, merge if new one has content
                    existing = seen_chapters[chapter_key]
                    if has_content:
                        # If existing has no content, replace it
                        if not (existing.sections or existing.parts or existing.user_notes):
                            seen_chapters[chapter_key] = chapter
                        else:
                            # Both have content, merge them
                            if chapter.user_notes and not existing.user_notes:
                                existing.user_notes = chapter.user_notes
                            
                            # Merge parts by part_number
                            for new_part in chapter.parts:
                                part_found = False
                                for existing_part in existing.parts:
                                    if existing_part.part_number == new_part.part_number:
                                        # Merge sections and update title if new one is longer
                                        existing_part.sections.extend(new_part.sections)
                                        if len(new_part.title) > len(existing_part.title):
                                            existing_part.title = new_part.title
                                        part_found = True
                                        break
                                if not part_found:
                                    existing.parts.append(new_part)
                            
                            existing.sections.extend(chapter.sections)
                else:
                    # New chapter
                    if has_content:
                        seen_chapters[chapter_key] = chapter
                        cleaned_chapters.append(chapter)
            
            # Clean up empty parts within each chapter
            for chapter in cleaned_chapters:
                # Filter out parts with no sections
                chapter.parts = [part for part in chapter.parts if part.sections]
                logger.debug(f"Chapter {chapter.chapter_number} has {len(chapter.parts)} parts with content")
            
            all_chapters = cleaned_chapters
            logger.info(f"Cleaned up chapters: {len(all_chapters)} unique chapters with content")
            
            # Process references and metadata for all sections
            logger.info("\nExtracting references and metadata...")
            for chapter in all_chapters:
                logger.info(f"\nChapter {chapter.chapter_number}: {chapter.title}")
                logger.info(f"  Total sections: {len(chapter.sections)}")
                
                for section in chapter.sections:
                    # Extract references
                    reference_extractor.extract_and_attach_references(section)
                    
                    # Collect metadata
                    metadata_collector.collect_section_metadata(section)
                    
                    # Log section info
                    total_subsections = len(section.subsections)
                    ref_count = (
                        len(section.references.internal_sections) +
                        len(section.references.tables) +
                        len(section.references.figures) +
                        len(section.references.external_documents)
                    )
                    
                    logger.info(
                        f"    Section {section.section_number}: {section.title[:50]}... "
                        f"(depth={section.depth}, subsections={total_subsections}, refs={ref_count})"
                    )
            
            # Create document model
            from src.config import DOCUMENT_TITLE, DOCUMENT_VERSION
            document = Document(
                title=DOCUMENT_TITLE,
                version=DOCUMENT_VERSION,
                chapters=all_chapters
            )
            
            # Export to JSON
            logger.info(f"\n Saving parsed document to {JSON_OUTPUT_FILE}...")
            json_output = document.model_dump_json(indent=2)
            JSON_OUTPUT_FILE.write_text(json_output)
            logger.info(f"✅ Saved {len(json_output)} characters to {JSON_OUTPUT_FILE}")
            
            logger.info("\n" + "=" * 80)
            logger.info("Phase 2 Testing Complete!")
            logger.info("=" * 80)
            logger.info(f"\nParsed {len(all_chapters)} chapter(s)")
            logger.info(f"Output saved to: {JSON_OUTPUT_FILE}")
            logger.info("\nNext steps:")
            logger.info("  - Phase 3: Enhance reference extraction")
            logger.info("  - Phase 4: Add table/figure extraction with Camelot")
            logger.info("  - Phase 5: Full document processing & optimization")
            
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        logger.error("\nPlease provide the path to your PDF file:")
        logger.error("  python -m src.main <path_to_pdf>")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


def test_pdf_extraction(pdf_path: str, num_pages: int = 5) -> None:
    """Test PDF extraction on sample pages (Phase 1).
    
    Args:
        pdf_path: Path to PDF file
        num_pages: Number of pages to extract (default: 5)
    """
    logger.info("=" * 80)
    logger.info("Phase 1: Core PDF Extraction Testing")
    logger.info("=" * 80)
    
    try:
        # Initialize PDF extractor
        with PDFExtractor(pdf_path) as extractor:
            total_pages = extractor.get_page_count()
            logger.info(f"PDF loaded successfully: {total_pages} pages")
            
            # Limit to available pages
            pages_to_extract = min(num_pages, total_pages)
            logger.info(f"Extracting first {pages_to_extract} pages...")
            
            # Extract text from sample pages
            for page_num in range(pages_to_extract):
                logger.info(f"\n--- Page {page_num + 1} ---")
                
                # Extract plain text
                text = extractor.extract_page_text(page_num)
                logger.info(f"Plain text extraction: {len(text)} characters")
                
                # Show first 500 characters as preview
                preview = text[:500].replace('\n', ' ')
                logger.info(f"Preview: {preview}...")
                
                # Extract text blocks with position info
                blocks = extractor.extract_page_text_with_blocks(page_num)
                logger.info(f"Text blocks extracted: {len(blocks)} blocks")
                
                # Show sample blocks
                if blocks:
                    logger.info("Sample text blocks:")
                    for i, block in enumerate(blocks[:3]):
                        logger.info(
                            f"  Block {i+1}: "
                            f"pos=({block['x0']:.1f},{block['y0']:.1f}), "
                            f"size={block['size']:.1f}, "
                            f"text='{block['text'][:50]}...'"
                        )
                
                # Check for images
                images = extractor.get_images_on_page(page_num)
                if images:
                    logger.info(f"Images found: {len(images)}")
                    for img in images:
                        logger.info(f"  Image {img['index']}: xref={img['xref']}")
                else:
                    logger.info("No images found on this page")
            
            logger.info("\n" + "=" * 80)
            logger.info("Phase 1 Testing Complete!")
            logger.info("=" * 80)
            logger.info("\nNext steps:")
            logger.info("  - Phase 2: Implement structure parsing (section hierarchy)")
            logger.info("  - Phase 3: Implement reference extraction")
            logger.info("  - Phase 4: Add table/figure extraction")
            
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        logger.error("\nPlease provide the path to your PDF file:")
        logger.error("  python -m src.main <path_to_pdf>")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


def main() -> None:
    """Main function."""
    if len(sys.argv) < 2:
        logger.error("Usage: python -m src.main <path_to_pdf> [num_pages] [--phase1]")
        logger.error("Example: python -m src.main 2021_IBC.pdf 10")
        logger.error("         python -m src.main 2021_IBC.pdf 5 --phase1  (test Phase 1 only)")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    num_pages = 10  # Default for Phase 2
    phase1_only = False
    
    # Parse arguments
    for arg in sys.argv[2:]:
        if arg == "--phase1":
            phase1_only = True
        elif arg.isdigit():
            num_pages = int(arg)
    
    if phase1_only:
        test_pdf_extraction(pdf_path, num_pages)
    else:
        test_structure_parsing(pdf_path, num_pages)


if __name__ == "__main__":
    main()
