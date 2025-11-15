"""Direct Camelot test without imports."""

import camelot
from pathlib import Path
import sys


def test_page(pdf_path: str, page_num: int, flavor: str = "lattice"):
    """Test Camelot extraction directly."""
    print(f"\n{'='*80}")
    print(f"Testing {flavor} extraction on page {page_num}")
    print(f"{'='*80}\n")
    
    try:
        if flavor == "lattice":
            kwargs = {
                "pages": str(page_num),
                "flavor": "lattice",
                "strip_text": '\n',
                "line_scale": 40,
                "process_background": True,
                "line_tol": 2,
            }
        else:
            kwargs = {
                "pages": str(page_num),
                "flavor": "stream",
                "strip_text": '\n',
                "edge_tol": 50,
                "row_tol": 2,
                "column_tol": 0,
            }
        
        tables = camelot.read_pdf(pdf_path, **kwargs)
        
        print(f"Extraction result: {len(tables)} table(s) found")
        print(f"Parsing report: {tables.parsing_report if hasattr(tables, 'parsing_report') else 'N/A'}\n")
        
        for i, table in enumerate(tables, 1):
            accuracy = getattr(table, 'accuracy', None)
            whitespace = getattr(table, 'whitespace', None)
            
            print(f"Table {i}:")
            print(f"  Shape: {table.df.shape}")
            print(f"  Accuracy: {accuracy:.2f}%" if accuracy else "  Accuracy: N/A")
            print(f"  Whitespace: {whitespace:.2f}%" if whitespace else "  Whitespace: N/A")
            
            if not table.df.empty:
                print(f"  First 3 rows:")
                print(table.df.head(3).to_string(index=False))
            print()
        
        return tables
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    # Find PDF
    pdf_candidates = [
        Path("2021_IBC.pdf"),
        Path("../2021_IBC.pdf"),
        Path("parser/2021_IBC.pdf"),
    ]
    
    pdf_path = None
    for candidate in pdf_candidates:
        if candidate.exists():
            pdf_path = candidate
            break
    
    if not pdf_path:
        print("Error: Could not find 2021_IBC.pdf")
        print("Please specify the PDF path:")
        pdf_input = input("> ").strip()
        pdf_path = Path(pdf_input)
        if not pdf_path.exists():
            print(f"Error: {pdf_path} does not exist")
            sys.exit(1)
    
    print(f"Using PDF: {pdf_path.absolute()}")
    
    # Test pages with known tables
    test_pages = [
        80,  # TABLE 307.1(1) - Hazardous Materials  
        81,  # TABLE 307.1(1) continued
    ]
    
    for page in test_pages:
        # Try both flavors
        for flavor in ["lattice", "stream"]:
            tables = test_page(str(pdf_path), page, flavor)
            if tables:
                print(f"✓ {flavor} succeeded for page {page}")
                break
        else:
            print(f"✗ Both flavors failed for page {page}")
        print()
