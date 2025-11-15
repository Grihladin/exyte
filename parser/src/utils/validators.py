"""Custom validation logic."""

import re


def is_valid_section_number(section_number: str) -> bool:
    """Check if a section number is valid.
    
    Args:
        section_number: Section number to validate
        
    Returns:
        True if valid, False otherwise
    """
    pattern = r'^\d+(?:\.\d+)*$'
    return bool(re.match(pattern, section_number))


def is_valid_chapter_number(chapter_number: int) -> bool:
    """Check if a chapter number is valid.
    
    Args:
        chapter_number: Chapter number to validate
        
    Returns:
        True if valid, False otherwise
    """
    return isinstance(chapter_number, int) and chapter_number > 0
