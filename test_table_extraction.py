"""Test script to debug table extraction issues."""

import json
import sys
from pathlib import Path

# Add parser to path
sys.path.insert(0, str(Path(__file__).parent / "parser" / "src"))

from parsers.table_extractor import TableExtractor
from parsers.pdf_extractor import PDFExtractor


def test_table_extraction(pdf_path: str, page_num: int):
    """Test table extraction on a specific page."""
    print(f"\n{'='*80}")
    print(f"Testing table extraction on page {page_num}")
    print(f"{'='*80}\n")
    
    # Extract text to see what's on the page
    with PDFExtractor(pdf_path) as extractor:
        text = extractor.extract_page_text(page_num - 1)
        print(f"Page text preview (first 500 chars):")
        print(text[:500])
        print(f"\n... (total {len(text)} characters)\n")
        
        # Check for TABLE mentions
        import re
        table_mentions = re.findall(r'TABLE\s+[\w\.\-()]+', text, re.IGNORECASE)
        print(f"Found {len(table_mentions)} TABLE mentions:")
        for mention in table_mentions[:10]:
            print(f"  - {mention}")
        if len(table_mentions) > 10:
            print(f"  ... and {len(table_mentions) - 10} more")
        print()
    
    # Try extracting tables
    extractor = TableExtractor(pdf_path)
    tables = extractor.extract_tables(page_num)
    
    print(f"Extraction result: {len(tables)} table(s) extracted\n")
    
    for i, table in enumerate(tables, 1):
        print(f"Table {i}:")
        print(f"  - Page: {table.page}")
        print(f"  - Accuracy: {table.accuracy:.2f}%" if table.accuracy else "  - Accuracy: N/A")
        print(f"  - Dimensions: {len(table.headers)} columns × {len(table.rows)} rows")
        print(f"  - Headers: {table.headers[:5]}{'...' if len(table.headers) > 5 else ''}")
        print(f"  - First row: {table.rows[0][:5] if table.rows else 'No rows'}{'...' if table.rows and len(table.rows[0]) > 5 else ''}")
        print()
    
    return tables


def find_problematic_pages(json_path: str):
    """Find pages where table hints were detected but extraction failed."""
    with open(json_path) as f:
        data = json.load(f)
    
    problematic = []
    for chapter in data['chapters']:
        for section in chapter.get('sections', []):
            if section.get('metadata', {}).get('has_table'):
                for table_ref in section.get('references', {}).get('tables', []):
                    if table_ref.get('table_data') is None:
                        page = section.get('metadata', {}).get('page_number', 'unknown')
                        problematic.append({
                            'section': section['section_number'],
                            'page': page,
                            'table_ref': table_ref['reference']
                        })
    
    return problematic


if __name__ == "__main__":
    # Find the PDF file
    pdf_path = Path("parser/output").parent.parent / "2021_IBC.pdf"
    
    if not pdf_path.exists():
        # Try alternative paths
        alternatives = [
            Path("2021_IBC.pdf"),
            Path("../2021_IBC.pdf"),
            Path("../../2021_IBC.pdf"),
        ]
        for alt in alternatives:
            if alt.exists():
                pdf_path = alt
                break
    
    if not pdf_path.exists():
        print(f"Error: Could not find PDF file")
        print(f"Searched: {pdf_path}")
        sys.exit(1)
    
    print(f"Using PDF: {pdf_path}")
    
    # Test specific pages known to have tables
    test_pages = [
        80,  # TABLE 307.1(1) - Hazardous Materials
        81,  # TABLE 307.1(1) continued
        82,  # TABLE 307.1(2)
    ]
    
    for page in test_pages:
        try:
            test_table_extraction(str(pdf_path), page)
        except Exception as e:
            print(f"Error extracting from page {page}: {e}")
            import traceback
            traceback.print_exc()
    
    # Find and report problematic pages
    json_path = Path("parser/output/parsed_document.json")
    if json_path.exists():
        print(f"\n{'='*80}")
        print("Analyzing problematic table extractions...")
        print(f"{'='*80}\n")
        
        problematic = find_problematic_pages(str(json_path))
        print(f"Found {len(problematic)} tables that failed to extract:")
        for item in problematic[:20]:
            print(f"  - Section {item['section']} (page {item['page']}): {item['table_ref']}")
        if len(problematic) > 20:
            print(f"  ... and {len(problematic) - 20} more")
