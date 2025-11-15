"""PDF text extraction using PyMuPDF."""

import logging
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from .pdf_filters import HeaderFooterFilter

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text and structure from PDF documents."""
    
    def __init__(self, pdf_path: str | Path, remove_headers_footers: bool = True):
        """Initialize PDF extractor.
        
        Args:
            pdf_path: Path to PDF file
            remove_headers_footers: Whether to filter out repeated headers/footers
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        self.doc: Optional[fitz.Document] = None
        self.remove_headers_footers = remove_headers_footers
        
        # Known chapter-specific running headers to filter
        self.chapter_headers = {
            "SCOPE AND ADMINISTRATION",
            "DEFINITIONS",
            "OCCUPANCY CLASSIFICATION AND USE",
            "SPECIAL DETAILED REQUIREMENTS BASED ON USE AND OCCUPANCY",
            "GENERAL BUILDING HEIGHTS AND AREAS",
            "TYPES OF CONSTRUCTION",
            "FIRE AND SMOKE PROTECTION FEATURES",
            "INTERIOR FINISHES",
            "FIRE PROTECTION SYSTEMS",
            "MEANS OF EGRESS",
        }
        
        self.header_filter = HeaderFooterFilter(self)
        self._open_document()
    
    def _open_document(self) -> None:
        """Open PDF document."""
        try:
            self.doc = fitz.open(self.pdf_path)
            logger.info(f"Opened PDF: {self.pdf_path} ({len(self.doc)} pages)")
        except Exception as e:
            logger.error(f"Failed to open PDF: {e}")
            raise
    
    def close(self) -> None:
        """Close PDF document."""
        if self.doc:
            self.doc.close()
            self.doc = None
            logger.info("Closed PDF document")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def get_page_count(self) -> int:
        """Get total number of pages.
        
        Returns:
            Number of pages in document
        """
        if not self.doc:
            raise ValueError("Document not open")
        return len(self.doc)
    
    def extract_page_text(self, page_num: int) -> str:
        """Extract text from a single page.
        
        Args:
            page_num: Page number (0-indexed)
            
        Returns:
            Extracted text content
        """
        if not self.doc:
            raise ValueError("Document not open")
        
        if page_num < 0 or page_num >= len(self.doc):
            raise ValueError(f"Invalid page number: {page_num}")
        
        try:
            page = self.doc[page_num]
            text = page.get_text()
            
            # Filter headers/footers if enabled
            if self.remove_headers_footers:
                text = self.header_filter.filter_text(text)
            
            logger.debug(f"Extracted text from page {page_num + 1} ({len(text)} chars)")
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from page {page_num + 1}: {e}")
            raise
    
    def extract_page_text_with_blocks(self, page_num: int) -> list[dict]:
        """Extract text blocks with position information.
        
        Args:
            page_num: Page number (0-indexed)
            
        Returns:
            List of text blocks with position data
            Each block is a dict with keys: x0, y0, x1, y1, text, block_no, type
        """
        if not self.doc:
            raise ValueError("Document not open")
        
        if page_num < 0 or page_num >= len(self.doc):
            raise ValueError(f"Invalid page number: {page_num}")
        
        try:
            page = self.doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            
            text_blocks = []
            for block in blocks:
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text_blocks.append({
                                "x0": span["bbox"][0],
                                "y0": span["bbox"][1],
                                "x1": span["bbox"][2],
                                "y1": span["bbox"][3],
                                "text": span["text"],
                                "size": span["size"],
                                "font": span["font"],
                                "flags": span["flags"],
                            })
            
            logger.debug(f"Extracted {len(text_blocks)} text blocks from page {page_num + 1}")
            return text_blocks
        except Exception as e:
            logger.error(f"Failed to extract text blocks from page {page_num + 1}: {e}")
            raise

    def extract_page_lines_with_fonts(self, page_num: int) -> list[dict]:
        """Extract line-level text with basic font information."""
        if not self.doc:
            raise ValueError("Document not open")
        if page_num < 0 or page_num >= len(self.doc):
            raise ValueError(f"Invalid page number: {page_num}")
        try:
            page = self.doc[page_num]
            blocks = page.get_text("dict").get("blocks", [])
            lines_info: list[dict] = []
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    if not spans:
                        continue
                    line_text = ''.join(span.get("text", "") for span in spans).strip()
                    if not line_text:
                        continue
                    sizes = [span.get("size") for span in spans if span.get("size")]
                    if not sizes:
                        continue
                    max_size = max(sizes)
                    dominant_span = max(
                        spans,
                        key=lambda span: len(span.get("text", "").strip()),
                    )
                    is_bold = any(
                        (span.get("flags", 0) & 2) or
                        ("Bold" in span.get("font", "") or "Black" in span.get("font", ""))
                        for span in spans
                    )
                    lines_info.append({
                        "text": line_text,
                        "max_size": float(max_size),
                        "font": dominant_span.get("font"),
                        "is_bold": is_bold,
                    })
            return lines_info
        except Exception as e:
            logger.error(f"Failed to extract line features from page {page_num + 1}: {e}")
            raise
    
    def extract_all_text(self, start_page: int = 0, end_page: Optional[int] = None) -> str:
        """Extract text from all pages or a range of pages.
        
        Args:
            start_page: Starting page number (0-indexed)
            end_page: Ending page number (0-indexed, exclusive). None means all pages.
            
        Returns:
            Combined text content from all pages
        """
        if not self.doc:
            raise ValueError("Document not open")
        
        if end_page is None:
            end_page = len(self.doc)
        
        all_text = []
        for page_num in range(start_page, end_page):
            text = self.extract_page_text(page_num)
            all_text.append(text)
            
            # Log progress every 100 pages
            if (page_num + 1) % 100 == 0:
                logger.info(f"Processed {page_num + 1} pages...")
        
        combined_text = "\n\n".join(all_text)
        logger.info(f"Extracted text from {end_page - start_page} pages ({len(combined_text)} chars)")
        return combined_text
    
    def get_images_on_page(self, page_num: int) -> list[dict]:
        """Get list of images on a page.
        
        Args:
            page_num: Page number (0-indexed)
            
        Returns:
            List of image metadata dictionaries
        """
        if not self.doc:
            raise ValueError("Document not open")
        
        if page_num < 0 or page_num >= len(self.doc):
            raise ValueError(f"Invalid page number: {page_num}")
        
        try:
            page = self.doc[page_num]
            images = page.get_images()
            
            image_list = []
            for img_index, img in enumerate(images):
                xref = img[0]
                image_list.append({
                    "xref": xref,
                    "index": img_index,
                    "page": page_num,
                })
            
            logger.debug(f"Found {len(image_list)} images on page {page_num + 1}")
            return image_list
        except Exception as e:
            logger.error(f"Failed to get images from page {page_num + 1}: {e}")
            raise
    
    def extract_image(self, xref: int) -> dict:
        """Extract image data by xref.
        
        Args:
            xref: Image xref number
            
        Returns:
            Dictionary with image data and metadata
        """
        if not self.doc:
            raise ValueError("Document not open")
        
        try:
            base_image = self.doc.extract_image(xref)
            return {
                "data": base_image["image"],
                "extension": base_image["ext"],
                "width": base_image.get("width"),
                "height": base_image.get("height"),
                "colorspace": base_image.get("colorspace"),
            }
        except Exception as e:
            logger.error(f"Failed to extract image {xref}: {e}")
            raise
