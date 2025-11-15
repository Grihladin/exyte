"""Formatter utilities for text processing."""

import re


def clean_text(text: str) -> str:
    """Clean and normalize text.
    
    Args:
        text: Raw text to clean
        
    Returns:
        Cleaned text
    """
    # Remove TOC formatting: dots and page numbers like " . . . . . 1-1"
    text = re.sub(r'\s+\.(?:\s+\.)+\s+[\d\-]+\s*$', '', text)
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


def extract_section_depth(section_number: str) -> int:
    """Calculate section depth from section number.
    
    Args:
        section_number: Section number (e.g., "307", "307.1", "307.1.1")
        
    Returns:
        Depth level (0 for base sections, 1+ for subsections)
    """
    return section_number.count('.')


def normalize_section_number(section_number: str) -> str:
    """Normalize section number format.
    
    Args:
        section_number: Section number to normalize
        
    Returns:
        Normalized section number
    """
    return section_number.strip()
