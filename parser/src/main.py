"""Main entry point for PDF parser - Phase 2: Structure Parsing."""

import logging
import sys
from pathlib import Path

from src.config import (
    LOG_LEVEL,
    LOG_FORMAT,
    JSON_OUTPUT_FILE,
    DEFAULT_PDF_PATH,
    DEFAULT_START_PAGE_INDEX,
    DEFAULT_PAGE_COUNT,
)
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


def test_structure_parsing(pdf_path: str, num_pages: int = 10, start_page: int = 0) -> None:
    """Test PDF structure parsing on sample pages.
    
    Args:
        pdf_path: Path to PDF file
        num_pages: Number of pages to parse (default: 10)
        start_page: Zero-based page index to start parsing from
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
            if start_page >= total_pages:
                logger.error(
                    f"Start page ({start_page + 1}) is beyond total pages ({total_pages})."
                )
                return
            pages_to_parse = min(num_pages, total_pages - start_page)
            start_display = start_page + 1
            end_display = start_display + pages_to_parse - 1
            logger.info(
                f"Parsing {pages_to_parse} page(s) for structure (pages {start_display}-{end_display})..."
            )
            
            all_chapters = []
            all_orphan_sections = []
            
            # Parse pages for structure
            for page_offset in range(pages_to_parse):
                page_num = start_page + page_offset
                logger.info(f"\n--- Processing Page {page_num + 1} ---")
                
                # Extract text
                text = extractor.extract_page_text(page_num)
                line_features = extractor.extract_page_lines_with_fonts(page_num)
                
                # Parse structure
                chapters, orphan_sections = structure_parser.parse_page_structure(
                    text,
                    page_num + 1,
                    line_features=line_features,
                )
                
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
                    bool(chapter.user_notes)
                )
                
                if chapter_key in seen_chapters:
                    # Chapter already exists, merge if new one has content
                    existing = seen_chapters[chapter_key]
                    if has_content:
                        # If existing has no content, replace it
                        if not (existing.sections or existing.user_notes):
                            seen_chapters[chapter_key] = chapter
                        else:
                            # Both have content, merge them
                            if chapter.user_notes and not existing.user_notes:
                                existing.user_notes = chapter.user_notes
                            existing.sections.extend(chapter.sections)
                else:
                    # New chapter
                    if has_content:
                        seen_chapters[chapter_key] = chapter
                        cleaned_chapters.append(chapter)
            
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
                    ref_count = (
                        len(section.references.internal_sections) +
                        len(section.references.tables) +
                        len(section.references.figures) +
                        len(section.references.external_documents)
                    )
                    
                    logger.info(
                        f"    Section {section.section_number}: {section.title[:50]}... "
                        f"(depth={section.depth}, refs={ref_count})"
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


def test_pdf_extraction(pdf_path: str, num_pages: int = 5, start_page: int = 0) -> None:
    """Test PDF extraction on sample pages (Phase 1).
    
    Args:
        pdf_path: Path to PDF file
        num_pages: Number of pages to extract (default: 5)
        start_page: Zero-based page index to start extraction from
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
            if start_page >= total_pages:
                logger.error(
                    f"Start page ({start_page + 1}) is beyond total pages ({total_pages})."
                )
                return
            pages_to_extract = min(num_pages, total_pages - start_page)
            start_display = start_page + 1
            end_display = start_display + pages_to_extract - 1
            logger.info(
                f"Extracting {pages_to_extract} page(s) (pages {start_display}-{end_display})..."
            )
            
            # Extract text from sample pages
            for page_offset in range(pages_to_extract):
                page_num = start_page + page_offset
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
    args = sys.argv[1:]
    pdf_path: str | Path = DEFAULT_PDF_PATH
    num_pages = DEFAULT_PAGE_COUNT
    start_page = DEFAULT_START_PAGE_INDEX
    phase1_only = False
    
    # Allow overriding defaults via CLI
    processed_args = list(args)
    if processed_args and not processed_args[0].startswith('-') and not processed_args[0].isdigit():
        pdf_path = processed_args.pop(0)
    elif not processed_args and not DEFAULT_PDF_PATH.exists():
        logger.error(
            "Default PDF not found at %s and no path argument was provided.",
            DEFAULT_PDF_PATH,
        )
        sys.exit(1)
    
    for arg in processed_args:
        if arg == "--phase1":
            phase1_only = True
        elif arg.startswith("--start="):
            value = arg.split("=", 1)[1]
            try:
                page_number = int(value)
                if page_number < 1:
                    raise ValueError
                start_page = page_number - 1
            except ValueError:
                logger.error(f"Invalid --start value '{value}'. Must be a positive integer.")
                sys.exit(1)
        elif arg.isdigit():
            num_pages = int(arg)
        else:
            logger.error(f"Unrecognized argument: {arg}")
            logger.error(
                "Usage: python -m src.main [pdf_path] [num_pages] [--start=<page>] [--phase1]"
            )
            sys.exit(1)
    
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    logger.info(
        "Using PDF: %s (pages %d-%d, total %d pages to parse)",
        pdf_path,
        start_page + 1,
        start_page + num_pages,
        num_pages,
    )
    
    if phase1_only:
        test_pdf_extraction(pdf_path, num_pages, start_page)
    else:
        test_structure_parsing(pdf_path, num_pages, start_page)


if __name__ == "__main__":
    main()
