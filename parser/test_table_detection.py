#!/usr/bin/env python3
"""Quick test script to verify PyMuPDF table detection works correctly."""

import fitz
from pathlib import Path

# Update this to your PDF path
PDF_PATH = "sample.pdf"  # or whatever your PDF file is called


def test_table_detection(pdf_path: str, page_num: int = 0):
    """Test PyMuPDF's find_tables() on a specific page."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]

    print(f"\n=== Testing page {page_num + 1} ===")
    print(f"Page size: {page.rect}")

    # Extract text to check for TABLE keywords
    text = page.get_text()
    table_keywords = [line for line in text.split("\n") if "TABLE" in line.upper()]
    print(f"\nFound {len(table_keywords)} lines with 'TABLE' keyword:")
    for kw in table_keywords[:5]:  # Show first 5
        print(f"  - {kw.strip()}")

    # Use find_tables() to detect actual tables
    tables = page.find_tables()

    if tables and tables.tables:
        print(f"\nPyMuPDF detected {len(tables.tables)} table(s):")
        for i, table in enumerate(tables):
            print(f"\n  Table {i+1}:")
            print(f"    BBox: {table.bbox}")
            print(f"    Rows: {table.row_count}")
            print(f"    Columns: {table.col_count}")

            # Show a preview of the table content
            try:
                extracted = table.extract()
                if extracted:
                    print(f"    First row: {extracted[0][:3]}...")  # Show first 3 cells
            except Exception as e:
                print(f"    (Could not extract content: {e})")
    else:
        print("\nPyMuPDF detected NO tables on this page")
        print("(This is expected if the page doesn't actually contain a table)")

    doc.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Try to find a PDF in common locations
        possible_paths = [
            "sample.pdf",
            "test.pdf",
            "document.pdf",
            "input.pdf",
        ]
        pdf_path = None
        for p in possible_paths:
            if Path(p).exists():
                pdf_path = p
                break

        if not pdf_path:
            print("Usage: python test_table_detection.py <pdf_path> [page_number]")
            print("\nOr place a PDF file named 'sample.pdf' in the current directory")
            sys.exit(1)

    page_num = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    print(f"Testing table detection on: {pdf_path}")
    test_table_detection(pdf_path, page_num)
