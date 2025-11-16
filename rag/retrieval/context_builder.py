"""Helpers to expand retrieved sections with surrounding context."""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Set

from rag.database.connection import get_sync_connection
from rag.retrieval.types import SectionResult


class ContextBuilder:
    def __init__(self, *, include_parents: bool = True, include_children: bool = True) -> None:
        self.include_parents = include_parents
        self.include_children = include_children

    def build(self, sections: Sequence[SectionResult]) -> Dict[str, List[SectionResult]]:
        base = list(sections)
        if not base:
            return {"sections": [], "parents": [], "children": []}

        with get_sync_connection() as conn:
            parents: Dict[int, SectionResult] = {}
            children: Dict[int, SectionResult] = {}

            if self.include_parents:
                parent_ids = {section.parent_section_id for section in base if section.parent_section_id}
                parents = self._fetch_sections(conn, parent_ids)

            if self.include_children:
                target_ids = {section.id for section in base}
                children = self._fetch_children(conn, target_ids)

        return {
            "sections": base,
            "parents": list(parents.values()),
            "children": list(children.values()),
        }

    def _fetch_sections(self, conn, section_ids: Iterable[int]) -> Dict[int, SectionResult]:
        ids = [section_id for section_id in section_ids if section_id]
        if not ids:
            return {}
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

    def _fetch_children(self, conn, parent_ids: Set[int]) -> Dict[int, SectionResult]:
        if not parent_ids:
            return {}
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
