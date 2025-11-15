"""PDF text extraction using PyMuPDF."""

import logging
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


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
        self.common_headers_footers: set[str] = set()
        
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
    
    def _detect_headers_footers(self, sample_size: int = 10) -> None:
        """Detect common headers/footers by analyzing sample pages.
        
        Args:
            sample_size: Number of pages to sample for detection
        """
        if not self.doc or not self.remove_headers_footers:
            return
        
        # Sample pages throughout the document
        total_pages = len(self.doc)
        step = max(1, total_pages // sample_size)
        sample_pages = range(0, min(total_pages, sample_size * step), step)
        
        # Collect text blocks from each sample page
        page_blocks = []
        for page_num in sample_pages:
            try:
                blocks = self.extract_page_text_with_blocks(page_num)
                # Group by vertical position (Y coordinate)
                top_blocks = [b for b in blocks if b['y0'] < 100]  # Top 100 pixels
                bottom_blocks = [b for b in blocks if b['y0'] > 700]  # Bottom area
                page_blocks.append({
                    'top': ' '.join(b['text'] for b in top_blocks),
                    'bottom': ' '.join(b['text'] for b in bottom_blocks)
                })
            except:
                continue
        
        # Find text that appears in most pages (>50%)
        threshold = len(page_blocks) * 0.5
        
        # Check top text
        top_texts = [p['top'] for p in page_blocks if p['top'].strip()]
        if top_texts:
            from collections import Counter
            common_top = [text for text, count in Counter(top_texts).items() 
                         if count >= threshold]
            self.common_headers_footers.update(common_top)
        
        # Check bottom text
        bottom_texts = [p['bottom'] for p in page_blocks if p['bottom'].strip()]
        if bottom_texts:
            from collections import Counter
            common_bottom = [text for text, count in Counter(bottom_texts).items() 
                           if count >= threshold]
            self.common_headers_footers.update(common_bottom)
        
        # Also add known patterns from the image (copyright notice)
        copyright_patterns = [
            "Copyright © 2020 ICC. ALL RIGHTS RESERVED.",
            "INTERNATIONAL CODE COUNCIL",
            "2021 INTERNATIONAL BUILDING CODE®",
        ]
        self.common_headers_footers.update(copyright_patterns)
        
        if self.common_headers_footers:
            logger.info(f"Detected {len(self.common_headers_footers)} common header/footer patterns")
    
    def _filter_headers_footers(self, text: str) -> str:
        """Remove detected headers/footers from text.
        
        Args:
            text: Text to filter
            
        Returns:
            Filtered text
        """
        if not self.remove_headers_footers or not text:
            return text
        
        # Initialize detection if not done
        if not self.common_headers_footers and self.doc:
            self._detect_headers_footers()
        
        # First, remove large copyright blocks that span multiple lines
        # The copyright text typically starts with "Copyright © 2020 ICC" and ends with order number
        copyright_start_patterns = ["Copyright © 2020 ICC", "Copyright © 2020 ICC."]
        copyright_end_patterns = [
            "101167924",  # The order number at the end
            "THEREUNDER.",
            "PENALTIES THEREUNDER"
        ]
        
        for start_pattern in copyright_start_patterns:
            while start_pattern in text:
                start_idx = text.find(start_pattern)
                # Find the end of this copyright block
                end_idx = -1
                for end_pattern in copyright_end_patterns:
                    temp_idx = text.find(end_pattern, start_idx)
                    if temp_idx != -1:
                        # Include the end pattern in removal
                        end_idx = temp_idx + len(end_pattern)
                        # Skip trailing whitespace and numbers
                        while end_idx < len(text) and (text[end_idx].isspace() or text[end_idx].isdigit()):
                            end_idx += 1
                        break
                
                if end_idx > start_idx:
                    # Remove the entire copyright block
                    text = text[:start_idx] + text[end_idx:]
                else:
                    # If we can't find the end, remove to end of paragraph
                    next_double_newline = text.find('\n\n', start_idx)
                    if next_double_newline != -1:
                        text = text[:start_idx] + text[next_double_newline:]
                    else:
                        # Just remove to end
                        text = text[:start_idx]
                    break
        
        # Now filter line by line for remaining header/footer patterns
        lines = text.split('\n')
        filtered_lines = []
        prev_line_was_chapter = False
        
        for line in lines:
            line_stripped = line.strip()
            # Skip empty lines
            if not line_stripped:
                continue
                
            # Skip if line matches any header/footer pattern
            should_skip = False
            for pattern in self.common_headers_footers:
                if pattern in line_stripped or line_stripped in pattern:
                    should_skip = True
                    break
            
            # Skip if line matches chapter headers (running headers)
            # BUT don't skip if previous line was a CHAPTER heading (this is the actual title)
            if not should_skip and line_stripped in self.chapter_headers:
                if not prev_line_was_chapter:
                    should_skip = True
            
            # Also skip lines that look like page numbers or section numbers at edges
            if line_stripped and len(line_stripped) < 5 and line_stripped.replace('-', '').replace('®', '').isdigit():
                should_skip = True
            
            if not should_skip:
                filtered_lines.append(line)
                # Track if this line is a CHAPTER heading
                prev_line_was_chapter = line_stripped.startswith('CHAPTER ')
            else:
                prev_line_was_chapter = False
        
        return '\n'.join(filtered_lines)
    
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
                text = self._filter_headers_footers(text)
            
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
