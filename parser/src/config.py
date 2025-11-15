"""Configuration settings for PDF parser."""

from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Input/Output directories
OUTPUT_DIR = PROJECT_ROOT / "output"
IMAGES_DIR = OUTPUT_DIR / "images"
JSON_OUTPUT_FILE = OUTPUT_DIR / "parsed_document.json"

# Ensure output directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

# Logging configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Processing configuration
PROGRESS_LOG_INTERVAL = 100  # Log progress every N pages

# PDF document info
DOCUMENT_TITLE = "2021 International Building Code"
DOCUMENT_VERSION = "2021"
