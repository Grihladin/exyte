"""Regex patterns for PDF document parsing."""

import re
from typing import Dict, Pattern


# Chapter patterns
# Must be standalone line: "CHAPTER 1" not "Chapter 1 is in two parts..."
CHAPTER_PATTERN: Pattern = re.compile(r'^CHAPTER\s+(\d+)\s*$', re.IGNORECASE)

# Part pattern (e.g., "PART 1—SCOPE AND APPLICATION")
PART_PATTERN: Pattern = re.compile(r'^PART\s+(\d+)[—\-]\s*(.+)', re.IGNORECASE)

# User notes pattern (starts with "User notes:")
USER_NOTES_PATTERN: Pattern = re.compile(r'^User notes:', re.IGNORECASE)

# Section header pattern (e.g., "SECTION 101")
SECTION_HEADER_PATTERN: Pattern = re.compile(r'^SECTION\s+(\d+)', re.IGNORECASE)

# Section patterns
# Format: [PREFIX] SECTION_NUMBER Title. Rest of text...
# Title is everything up to the first period
PREFIX_SECTION_PATTERN: Pattern = re.compile(
    r'^\[([A-Z]+)\]\s+(\d+(?:\.\d+)*)\s+(.+?)\.\s*'
)
SECTION_PATTERN: Pattern = re.compile(
    r'^(\d+(?:\.\d+)*)\s+(.+)$'
)

# Numbered list items
NUMBERED_ITEM_PATTERN: Pattern = re.compile(r'^\s*(\d+)\.\s+(.+)$')

# Reference patterns
INTERNAL_SECTION_PATTERN: Pattern = re.compile(
    r'Sections?\s+\d+(?:\.\d+)*(?:\s+(?:and|through|to)\s+\d+(?:\.\d+)*)*',
    re.IGNORECASE
)

# Table references - multiple patterns to catch variations
TABLE_PATTERN_1: Pattern = re.compile(
    r'TABLE\s+\d+(?:\.\d+)*(?:\(\d+\))?',
    re.IGNORECASE
)
TABLE_PATTERN_2: Pattern = re.compile(
    r'Tables?\s+\d+(?:\.\d+)*(?:\(\d+\))?',
    re.IGNORECASE
)

# Chapter references
CHAPTER_REF_PATTERN: Pattern = re.compile(r'Chapter\s+\d+', re.IGNORECASE)

# Figure references
FIGURE_PATTERN_1: Pattern = re.compile(
    r'Figures?\s+\d+(?:\.\d+)*(?:\([0-9]+\))?',
    re.IGNORECASE
)
FIGURE_PATTERN_2: Pattern = re.compile(
    r'Fig\.\s+\d+(?:\.\d+)*',
    re.IGNORECASE
)

# External document references - specific codes first, then general
EXTERNAL_DOC_PATTERNS: list[Pattern] = [
    re.compile(r'International\s+Fire\s+Code', re.IGNORECASE),
    re.compile(r'International\s+Fuel\s+Gas\s+Code', re.IGNORECASE),
    re.compile(r'International\s+Mechanical\s+Code', re.IGNORECASE),
    re.compile(r'International\s+Plumbing\s+Code', re.IGNORECASE),
    re.compile(r'International\s+\w+\s+Code', re.IGNORECASE),
]


# Compiled patterns dictionary for easy access
PATTERNS: Dict[str, Pattern | list[Pattern]] = {
    'chapter': CHAPTER_PATTERN,
    'part': PART_PATTERN,
    'user_notes': USER_NOTES_PATTERN,
    'section_header': SECTION_HEADER_PATTERN,
    'prefix_section': PREFIX_SECTION_PATTERN,
    'section': SECTION_PATTERN,
    'numbered_item': NUMBERED_ITEM_PATTERN,
    'internal_section': INTERNAL_SECTION_PATTERN,
    'table': [TABLE_PATTERN_1, TABLE_PATTERN_2],
    'chapter_ref': CHAPTER_REF_PATTERN,
    'figure': [FIGURE_PATTERN_1, FIGURE_PATTERN_2],
    'external_doc': EXTERNAL_DOC_PATTERNS,
}
