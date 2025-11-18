"""Reference extraction and classification."""

import logging
import re
from typing import Optional

from ..models import (
    References,
    InternalSectionReference,
    FigureReference,
    ExternalDocumentReference,
    Position,
)
from ..utils.patterns import PATTERNS


logger = logging.getLogger(__name__)


class ReferenceExtractor:
    """Extract and classify references from text."""
    
    def __init__(self):
        """Initialize reference extractor."""
        pass
    
    def extract_references(self, text: str) -> References:
        """Extract all references from text.
        
        Args:
            text: Text to scan for references
            
        Returns:
            References object with all found references
        """
        references = References()
        
        if not text:
            return references
        
        # Extract each type of reference
        references.internal_sections = self._extract_internal_sections(text)
        references.figures = self._extract_figures(text)
        references.external_documents = self._extract_external_documents(text)
        
        total_refs = (
            len(references.internal_sections) +
            len(references.figures) +
            len(references.external_documents)
        )
        
        if total_refs > 0:
            logger.debug(
                f"Extracted {total_refs} references: "
                f"{len(references.internal_sections)} sections, "
                f"{len(references.figures)} figures, "
                f"{len(references.external_documents)} external"
            )
        
        return references
    
    def _extract_internal_sections(self, text: str) -> list[InternalSectionReference]:
        """Extract internal section references.
        
        Args:
            text: Text to scan
            
        Returns:
            List of internal section references
        """
        references = []
        pattern = PATTERNS['internal_section']
        
        for match in pattern.finditer(text):
            # Extract just the section numbers, remove "Section" prefix
            full_text = match.group(0)
            # Extract numbers: "Section 414" -> "414", "Sections 308.4.1 through 308.4.5" -> "308.4.1 through 308.4.5"
            # Handle case-insensitive: SECTION, Section, section
            normalized = re.sub(r'\b[Ss]ections?\s+', '', full_text, flags=re.IGNORECASE)
            
            ref = InternalSectionReference(
                reference=normalized,
                position=Position(start=match.start(), end=match.end())
            )
            references.append(ref)
        
        return references
    
    def _extract_figures(self, text: str) -> list[FigureReference]:
        """Extract figure references.
        
        Args:
            text: Text to scan
            
        Returns:
            List of figure references
        """
        references = []
        seen_positions = set()
        
        # Try multiple figure patterns
        for pattern in PATTERNS['figure']:
            for match in pattern.finditer(text):
                # Avoid duplicates from overlapping patterns
                pos = (match.start(), match.end())
                if pos in seen_positions:
                    continue
                seen_positions.add(pos)
                
                # Extract just the figure number, remove "Figure" or "Fig." prefix
                full_text = match.group(0)
                # "Figure 1.2" -> "1.2", "Fig. 3.4" -> "3.4", "FIGURE 5" -> "5"
                # Handle case-insensitive
                normalized = re.sub(r'\b[Ff]igures?\s+', '', full_text, flags=re.IGNORECASE)
                normalized = re.sub(r'\bFig\.\s+', '', normalized, flags=re.IGNORECASE)
                
                ref = FigureReference(
                    reference=normalized,
                    position=Position(start=match.start(), end=match.end())
                )
                references.append(ref)
        
        return references
    
    def _extract_external_documents(self, text: str) -> list[ExternalDocumentReference]:
        """Extract external document references.
        
        Args:
            text: Text to scan
            
        Returns:
            List of external document references
        """
        references = []
        seen_positions = set()
        
        # Try each external document pattern
        for pattern in PATTERNS['external_doc']:
            for match in pattern.finditer(text):
                # Avoid duplicates from overlapping patterns
                pos = (match.start(), match.end())
                if pos in seen_positions:
                    continue
                seen_positions.add(pos)
                
                ref = ExternalDocumentReference(
                    reference=match.group(0),
                    position=Position(start=match.start(), end=match.end())
                )
                references.append(ref)
        
        return references
    
    def extract_and_attach_references(self, section) -> None:
        """Extract references from section text and attach to section.
        
        Args:
            section: Section object to process (mutates in place)
        """
        existing_refs = section.references
        if section.text:
            new_refs = self.extract_references(section.text)
        else:
            new_refs = References()
        
        # Preserve any pre-attached references and merge with new ones
        new_refs.internal_sections = existing_refs.internal_sections + new_refs.internal_sections
        new_refs.table = existing_refs.table  # Preserve table IDs added during extraction
        new_refs.figures = existing_refs.figures  # Preserve figure IDs added during extraction
        new_refs.external_documents = existing_refs.external_documents + new_refs.external_documents
        section.references = new_refs
        
        # Also extract from numbered items
        for item in section.numbered_items:
            item_refs = self.extract_references(item.text)
            # Merge with section references
            section.references.internal_sections.extend(item_refs.internal_sections)
            # Note: figures are now list[str] (IDs), not FigureReference objects
            # Don't merge text figure references here - only actual extracted figures matter
            section.references.external_documents.extend(item_refs.external_documents)
