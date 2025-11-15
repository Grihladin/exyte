"""Verify Phase 1 implementation."""

import sys
from pathlib import Path

print("=" * 80)
print("Phase 1 Implementation Verification")
print("=" * 80)

# Test imports
print("\n1. Testing imports...")
try:
    from src.models import Document, Chapter, Section, References
    print("   ✅ Models imported successfully")
except ImportError as e:
    print(f"   ❌ Failed to import models: {e}")
    sys.exit(1)

try:
    from src.parsers import PDFExtractor
    print("   ✅ PDF Extractor imported successfully")
except ImportError as e:
    print(f"   ❌ Failed to import PDF Extractor: {e}")
    sys.exit(1)

try:
    from src.utils import PATTERNS
    print("   ✅ Patterns imported successfully")
except ImportError as e:
    print(f"   ❌ Failed to import patterns: {e}")
    sys.exit(1)

try:
    from src import config
    print("   ✅ Config imported successfully")
except ImportError as e:
    print(f"   ❌ Failed to import config: {e}")
    sys.exit(1)

# Test model creation
print("\n2. Testing Pydantic models...")
try:
    doc = Document(
        title="Test Document",
        version="2021",
        chapters=[]
    )
    print(f"   ✅ Document model created: {doc.title}")
    
    section = Section(
        section_number="307",
        title="Test Section",
        depth=0
    )
    print(f"   ✅ Section model created: {section.section_number} - {section.title}")
    
except Exception as e:
    print(f"   ❌ Failed to create models: {e}")
    sys.exit(1)

# Test regex patterns
print("\n3. Testing regex patterns...")
try:
    import re
    
    test_texts = [
        ("CHAPTER 3", "chapter"),
        ("[F] 307.1 Test Section", "prefix_section"),
        ("Section 414", "internal_section"),
        ("Table 307.1(1)", "table"),
        ("Figure 721.2.1.4(1)", "figure"),
    ]
    
    for text, pattern_name in test_texts:
        if pattern_name == "chapter":
            match = PATTERNS['chapter'].match(text)
        elif pattern_name == "prefix_section":
            match = PATTERNS['prefix_section'].match(text)
        elif pattern_name == "internal_section":
            match = PATTERNS['internal_section'].search(text)
        elif pattern_name == "table":
            for pattern in PATTERNS['table']:
                match = pattern.search(text)
                if match:
                    break
        elif pattern_name == "figure":
            for pattern in PATTERNS['figure']:
                match = pattern.search(text)
                if match:
                    break
        
        if match:
            print(f"   ✅ Pattern '{pattern_name}' matched: '{text}'")
        else:
            print(f"   ⚠️  Pattern '{pattern_name}' did not match: '{text}'")
    
except Exception as e:
    print(f"   ❌ Failed to test patterns: {e}")
    sys.exit(1)

# Check directory structure
print("\n4. Checking directory structure...")
dirs_to_check = [
    "src",
    "src/models",
    "src/parsers",
    "src/utils",
    "tests",
    "output",
    "output/images",
]

for dir_path in dirs_to_check:
    path = Path(dir_path)
    if path.exists():
        print(f"   ✅ {dir_path}/")
    else:
        print(f"   ❌ {dir_path}/ (missing)")

# Check key files
print("\n5. Checking key files...")
files_to_check = [
    "src/__init__.py",
    "src/main.py",
    "src/config.py",
    "src/models/__init__.py",
    "src/models/document.py",
    "src/models/references.py",
    "src/parsers/__init__.py",
    "src/parsers/pdf_extractor.py",
    "src/utils/__init__.py",
    "src/utils/patterns.py",
    "src/utils/formatters.py",
    "src/utils/validators.py",
    "pyproject.toml",
    "README.md",
]

for file_path in files_to_check:
    path = Path(file_path)
    if path.exists():
        print(f"   ✅ {file_path}")
    else:
        print(f"   ❌ {file_path} (missing)")

print("\n" + "=" * 80)
print("Phase 1 Verification Complete!")
print("=" * 80)
print("To test PDF extraction, run:")
print("  uv run python -m src.main <path_to_pdf> <num_pages>")
print("\nExample:")
print("  uv run python -m src.main 2021_IBC.pdf 5")
print("=" * 80)
