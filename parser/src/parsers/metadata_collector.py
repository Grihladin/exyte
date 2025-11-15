"""Metadata collection for sections."""

import logging
from typing import Optional

from ..models import Section, Metadata


logger = logging.getLogger(__name__)


class MetadataCollector:
    """Collect and aggregate metadata for document sections."""
    
    def __init__(self):
        """Initialize metadata collector."""
        pass
    
    def collect_section_metadata(self, section: Section) -> None:
        """Collect metadata for a section and its subsections.
        
        Args:
            section: Section to process (mutates in place)
        """
        # Count references
        table_count = len(section.references.tables)
        figure_count = len(section.references.figures)
        
        # Update metadata
        if section.metadata is None:
            section.metadata = Metadata(
                has_table=table_count > 0,
                has_figure=figure_count > 0,
                table_count=table_count,
                figure_count=figure_count,
                page_number="0"  # Will be updated during parsing
            )
        else:
            section.metadata.has_table = table_count > 0
            section.metadata.has_figure = figure_count > 0
            section.metadata.table_count = table_count
            section.metadata.figure_count = figure_count
        
        # Recursively process subsections
        for subsection in section.subsections:
            self.collect_section_metadata(subsection)
            
            # Aggregate child metadata to parent
            if subsection.metadata:
                section.metadata.table_count += subsection.metadata.table_count
                section.metadata.figure_count += subsection.metadata.figure_count
                section.metadata.has_table = section.metadata.has_table or subsection.metadata.has_table
                section.metadata.has_figure = section.metadata.has_figure or subsection.metadata.has_figure
        
        logger.debug(
            f"Section {section.section_number}: "
            f"{section.metadata.table_count} tables, "
            f"{section.metadata.figure_count} figures"
        )
    
    def update_page_ranges(self, section: Section, page_map: dict[str, str]) -> None:
        """Update page number ranges for sections.
        
        Args:
            section: Section to update
            page_map: Mapping of section numbers to page ranges
        """
        if section.section_number in page_map:
            if section.metadata:
                section.metadata.page_number = page_map[section.section_number]
        
        # Recursively update subsections
        for subsection in section.subsections:
            self.update_page_ranges(subsection, page_map)
