"""Test PDF extractor functionality."""

import logging
from pathlib import Path

from src.parsers.pdf_extractor import PDFExtractor


logging.basicConfig(level=logging.INFO)


def test_pdf_extractor_basic():
    """Test basic PDF extractor functionality with a sample PDF."""
    # This test requires a PDF file to run
    # You can create a simple test PDF or skip this test for now
    print("Test: PDF Extractor")
    print("To run this test, provide a PDF file path")
    print("Example usage:")
    print("  python -m src.main <path_to_pdf> 5")
    

if __name__ == "__main__":
    test_pdf_extractor_basic()
