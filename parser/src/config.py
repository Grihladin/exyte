"""Configuration settings for PDF parser."""

import os
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Input/Output directories
OUTPUT_DIR = PROJECT_ROOT / "output"
IMAGES_DIR = OUTPUT_DIR / "images"
TABLE_IMAGES_DIR = OUTPUT_DIR / "tables"
TABLE_REGIONS_FILE = OUTPUT_DIR / "table_regions.json"
JSON_OUTPUT_FILE = OUTPUT_DIR / "parsed_document.json"

# Default PDF parsing settings
DEFAULT_PDF_PATH = PROJECT_ROOT.parent / "2021_International_Building_Code.pdf"
DEFAULT_START_PAGE_NUMBER = 32  # Human-friendly numbering
DEFAULT_END_PAGE_NUMBER = 769
DEFAULT_START_PAGE_INDEX = DEFAULT_START_PAGE_NUMBER - 1  # Zero-based for extractor
DEFAULT_PAGE_COUNT = DEFAULT_END_PAGE_NUMBER - DEFAULT_START_PAGE_NUMBER + 1

# Ensure output directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)
TABLE_IMAGES_DIR.mkdir(exist_ok=True)

# Logging configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Processing configuration
PROGRESS_LOG_INTERVAL = 100  # Log progress every N pages

# PDF document info
DOCUMENT_TITLE = "2021 International Building Code"
DOCUMENT_VERSION = "2021"
