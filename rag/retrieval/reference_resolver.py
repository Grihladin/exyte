"""Resolve referenced tables, figures, and sections for retrieved context."""

from __future__ import annotations

from typing import Dict, List, Sequence

from rag.database.connection import get_sync_connection
from rag.retrieval.types import FigureResult, ReferenceBundle, SectionResult, TableResult


class ReferenceResolver:
    def resolve(self, section_ids: Sequence[int]) -> ReferenceBundle:
        if not section_ids:
            return ReferenceBundle(sections=[], tables=[], figures=[])

        with get_sync_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        source_section_id,
                        reference_type,
                        reference_text,
                        target_section_id
                    FROM section_references
                    WHERE source_section_id = ANY(%s)
                    """,
                    (list(section_ids),),
                )
                references = cur.fetchall()

            table_ids = [row[2] for row in references if row[1] == "table"]
            figure_ids = [row[2] for row in references if row[1] == "figure"]
            section_target_ids = [row[3] for row in references if row[1] == "section" and row[3]]

            tables = self._fetch_tables(conn, table_ids)
            figures = self._fetch_figures(conn, figure_ids)
            sections = self._fetch_sections(conn, section_target_ids)

        return ReferenceBundle(
            sections=list(sections.values()),
            tables=tables,
            figures=figures,
        )

    def _fetch_tables(self, conn, table_ids: Sequence[str]) -> List[TableResult]:
        identifiers = [table_id for table_id in table_ids if table_id]
        if not identifiers:
            return []
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    table_id,
                    table_name,
                    section_id,
                    markdown,
                    page_number
                FROM tables
                WHERE table_id = ANY(%s)
                """,
                (identifiers,),
            )
            rows = cur.fetchall()
        return [
            TableResult(
                id=row[0],
                table_id=row[1],
                table_name=row[2],
                section_id=row[3],
                markdown=row[4],
                page_number=row[5],
            )
            for row in rows
        ]

    def _fetch_figures(self, conn, figure_ids: Sequence[str]) -> List[FigureResult]:
        identifiers = [figure_id for figure_id in figure_ids if figure_id]
        if not identifiers:
            return []
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    figure_id,
                    section_id,
                    image_path,
                    page_number,
                    caption
                FROM figures
                WHERE figure_id = ANY(%s)
                """,
                (identifiers,),
            )
            rows = cur.fetchall()
        return [
            FigureResult(
                id=row[0],
                figure_id=row[1],
                section_id=row[2],
                image_path=row[3],
                page_number=row[4],
                caption=row[5],
            )
            for row in rows
        ]

    def _fetch_sections(self, conn, section_ids: Sequence[int]) -> Dict[int, SectionResult]:
        identifiers = [section_id for section_id in section_ids if section_id]
        if not identifiers:
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
                (identifiers,),
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
