"""Helpers to expand retrieved sections with surrounding context."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Sequence, Set

from rag.database.connection import get_sync_connection
from rag.retrieval.types import SectionResult

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Build enriched context by fetching parent and child sections.
    
    For better RAG results, this builder expands retrieved sections with:
    - Parent sections: Provide broader context and hierarchical information
    - Child sections: Provide detailed breakdowns and specifications
    
    This hierarchical expansion helps the LLM understand the structure
    and relationships between different parts of the building code.
    """

    def __init__(
        self,
        *,
        include_parents: bool = True,
        include_children: bool = True
    ) -> None:
        """
        Initialize context builder.
        
        Args:
            include_parents: Whether to fetch parent sections
            include_children: Whether to fetch child sections
        """
        self.include_parents = include_parents
        self.include_children = include_children

    def build(
        self,
        sections: Sequence[SectionResult]
    ) -> Dict[str, List[SectionResult]]:
        """
        Build enriched context from base sections.
        
        Args:
            sections: Base sections from retrieval
            
        Returns:
            Dictionary with keys:
            - "sections": Original sections
            - "parents": Parent sections for additional context
            - "children": Child sections for detailed information
        """
        base = list(sections)
        if not base:
            logger.debug("No base sections provided to context builder")
            return {"sections": [], "parents": [], "children": []}

        try:
            with get_sync_connection() as conn:
                parents: Dict[int, SectionResult] = {}
                children: Dict[int, SectionResult] = {}

                if self.include_parents:
                    parent_ids = {
                        section.parent_section_id
                        for section in base
                        if section.parent_section_id
                    }
                    if parent_ids:
                        parents = self._fetch_sections(conn, parent_ids)
                        logger.debug(f"Fetched {len(parents)} parent sections")

                if self.include_children:
                    target_ids = {section.id for section in base}
                    if target_ids:
                        children = self._fetch_children(conn, target_ids)
                        logger.debug(f"Fetched {len(children)} child sections")

            return {
                "sections": base,
                "parents": list(parents.values()),
                "children": list(children.values()),
            }
            
        except Exception as e:
            logger.error(f"Error building context: {e}", exc_info=True)
            # Return base sections even if context expansion fails
            return {"sections": base, "parents": [], "children": []}

    def _fetch_sections(
        self,
        conn,
        section_ids: Iterable[int]
    ) -> Dict[int, SectionResult]:
        """
        Fetch specific sections by ID.
        
        Args:
            conn: Database connection
            section_ids: IDs of sections to fetch
            
        Returns:
            Dictionary mapping section ID to SectionResult
        """
        ids = [section_id for section_id in section_ids if section_id]
        if not ids:
            return {}
        
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        s.id,
                        s.section_number,
                        s.title,
                        s.text,
                        s.metadata,
                        s.depth,
                        s.parent_section_id,
                        s.page_number,
                        c.id AS chapter_id,
                        c.chapter_number,
                        c.title AS chapter_title
                    FROM sections s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE s.id = ANY(%s)
                    """,
                    (ids,),
                )
                rows = cur.fetchall()

            return {
                row[0]: SectionResult(
                    id=row[0],
                    section_number=row[1],
                    title=row[2],
                    text=row[3],
                    metadata=row[4] or {},
                    depth=row[5],
                    parent_section_id=row[6],
                    page_number=row[7],
                    chapter_id=row[8],
                    chapter_number=row[9],
                    chapter_title=row[10],
                    score=0.0,
                )
                for row in rows
            }
        except Exception as e:
            logger.error(f"Error fetching sections: {e}", exc_info=True)
            return {}

    def _fetch_children(
        self,
        conn,
        parent_ids: Set[int]
    ) -> Dict[int, SectionResult]:
        """
        Fetch child sections for given parent IDs.
        
        Args:
            conn: Database connection
            parent_ids: IDs of parent sections
            
        Returns:
            Dictionary mapping child section ID to SectionResult
        """
        if not parent_ids:
            return {}
        
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        s.id,
                        s.section_number,
                        s.title,
                        s.text,
                        s.metadata,
                        s.depth,
                        s.parent_section_id,
                        s.page_number,
                        c.id AS chapter_id,
                        c.chapter_number,
                        c.title AS chapter_title
                    FROM sections s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE s.parent_section_id = ANY(%s)
                    """,
                    (list(parent_ids),),
                )
                rows = cur.fetchall()

            return {
                row[0]: SectionResult(
                    id=row[0],
                    section_number=row[1],
                    title=row[2],
                    text=row[3],
                    metadata=row[4] or {},
                    depth=row[5],
                    parent_section_id=row[6],
                    page_number=row[7],
                    chapter_id=row[8],
                    chapter_number=row[9],
                    chapter_title=row[10],
                    score=0.0,
                )
                for row in rows
            }
        except Exception as e:
            logger.error(f"Error fetching child sections: {e}", exc_info=True)
            return {}
