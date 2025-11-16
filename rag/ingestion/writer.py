"""Database writer for ingestion payloads."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Sequence

from psycopg import Connection
from psycopg.types.json import Json

from rag.database.connection import get_sync_connection
from rag.models import (
    DocumentPayload,
    FigurePayload,
    ReferencePayload,
    TablePayload,
    guess_section_number,
)

logger = logging.getLogger(__name__)


class DatabaseWriter:
    """Persist normalized document payloads into PostgreSQL."""

    def __init__(self) -> None:
        pass

    def write(self, document: DocumentPayload) -> int:
        """Insert a document and all related records. Returns the document ID."""

        with get_sync_connection() as conn:
            document_id = self._write_document(conn, document)
            conn.commit()
        return document_id

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #
    def _write_document(self, conn: Connection, document: DocumentPayload) -> int:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (title, version, metadata)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (
                    document.title,
                    document.version,
                    Json({"source_path": document.source_path} if document.source_path else {}),
                ),
            )
            document_id = cur.fetchone()[0]

            section_lookup: Dict[str, int] = {}
            section_page_index: Dict[str, List[int]] = defaultdict(list)
            table_to_section: Dict[str, int] = {}
            figure_to_section: Dict[str, int] = {}
            references_queue: List[tuple[int, ReferencePayload]] = []
            numbered_items_queue: List[tuple[int, int, str]] = []

            for chapter in document.chapters:
                cur.execute(
                    """
                    INSERT INTO chapters (document_id, chapter_number, title, user_notes)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (document_id, chapter.chapter_number, chapter.title, chapter.user_notes),
                )
                chapter_id = cur.fetchone()[0]

                depth_stack: List[tuple[int, int]] = []
                section_number_counts: Dict[str, int] = defaultdict(int)

                for section in chapter.sections:
                    while depth_stack and depth_stack[-1][0] >= section.depth:
                        depth_stack.pop()
                    parent_section_id = depth_stack[-1][1] if depth_stack else None

                    original_number = section.section_number
                    duplicate_count = section_number_counts[original_number]
                    section_number_counts[original_number] += 1
                    unique_section_number = (
                        original_number if duplicate_count == 0 else f"{original_number}-dup{duplicate_count + 1}"
                    )
                    metadata = dict(section.metadata or {})
                    if duplicate_count > 0:
                        metadata.setdefault("original_section_number", original_number)
                        metadata["duplicate_index"] = duplicate_count + 1
                        logger.debug(
                            "Chapter %s has duplicate section number %s – stored as %s",
                            chapter.chapter_number,
                            original_number,
                            unique_section_number,
                        )
                    else:
                        metadata.setdefault("original_section_number", original_number)

                    cur.execute(
                        """
                        INSERT INTO sections (
                            chapter_id,
                            parent_section_id,
                            section_number,
                            prefix,
                            title,
                            text,
                            depth,
                            page_number,
                            embedding,
                            metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            chapter_id,
                            parent_section_id,
                            unique_section_number,
                            section.prefix,
                            section.title,
                            section.text,
                            section.depth,
                            section.page_number,
                            section.embedding,
                            Json(metadata),
                        ),
                    )
                    section_id = cur.fetchone()[0]
                    depth_stack.append((section.depth, section_id))
                    section_lookup[unique_section_number] = section_id
                    section_lookup.setdefault(original_number, section_id)

                    if section.page_number:
                        section_page_index.setdefault(section.page_number, []).append(section_id)

                    for item in section.numbered_items:
                        numbered_items_queue.append((section_id, item.number, item.text))

                    for reference in section.references:
                        references_queue.append((section_id, reference))
                        if reference.reference_type == "table":
                            table_to_section.setdefault(reference.reference_text, section_id)
                        elif reference.reference_type == "figure":
                            figure_to_section.setdefault(reference.reference_text, section_id)

            self._insert_numbered_items(cur, numbered_items_queue)
            self._insert_references(cur, references_queue, section_lookup)
            self._insert_tables(cur, document.tables, table_to_section, section_lookup)
            self._insert_figures(cur, document.figures, figure_to_section, section_page_index)

        return document_id

    def _insert_numbered_items(self, cur, queue: Sequence[tuple[int, int, str]]) -> None:
        if not queue:
            return
        cur.executemany(
            """
            INSERT INTO numbered_items (section_id, number, text)
            VALUES (%s, %s, %s)
            """,
            queue,
        )

    def _insert_references(
        self,
        cur,
        queue: Sequence[tuple[int, ReferencePayload]],
        section_lookup: Dict[str, int],
    ) -> None:
        if not queue:
            return

        rows = []
        for source_section_id, reference in queue:
            if not reference.reference_text:
                continue
            target_section_id = None
            if reference.reference_type == "section":
                target_section_id = section_lookup.get(reference.reference_text)
            rows.append(
                (
                    source_section_id,
                    target_section_id,
                    reference.reference_type,
                    reference.reference_text,
                    reference.position_start,
                    reference.position_end,
                )
            )

        if not rows:
            return

        cur.executemany(
            """
            INSERT INTO section_references (
                source_section_id,
                target_section_id,
                reference_type,
                reference_text,
                position_start,
                position_end
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            rows,
        )

    def _insert_tables(
        self,
        cur,
        tables: Sequence[TablePayload],
        table_assignments: Dict[str, int],
        section_lookup: Dict[str, int],
    ) -> None:
        if not tables:
            return

        rows = []
        missing_tables: List[str] = []
        for table in tables:
            section_id = table_assignments.get(table.table_id)
            if section_id is None and table.section_number_hint:
                section_id = section_lookup.get(table.section_number_hint)
            if section_id is None:
                inferred = guess_section_number(table.table_id)
                if inferred:
                    section_id = section_lookup.get(inferred)
            if section_id is None:
                missing_tables.append(table.table_id)
            rows.append(
                (
                    table.table_id,
                    section_id,
                    Json(table.headers or []),
                    Json(table.rows or []),
                    table.page_number,
                    table.accuracy,
                    table.embedding,
                )
            )

        cur.executemany(
            """
            INSERT INTO tables (
                table_id,
                section_id,
                headers,
                rows,
                page_number,
                accuracy,
                embedding
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (table_id) DO UPDATE
                SET
                    section_id = EXCLUDED.section_id,
                    headers = EXCLUDED.headers,
                    rows = EXCLUDED.rows,
                    page_number = EXCLUDED.page_number,
                    accuracy = EXCLUDED.accuracy,
                    embedding = EXCLUDED.embedding
            """,
            rows,
        )
        if missing_tables:
            logger.debug(
                "Unable to associate %d tables with sections (examples: %s)",
                len(missing_tables),
                ", ".join(missing_tables[:3]),
            )

    def _insert_figures(
        self,
        cur,
        figures: Sequence[FigurePayload],
        figure_assignments: Dict[str, int],
        section_page_index: Dict[str, List[int]],
    ) -> None:
        if not figures:
            return

        rows = []
        missing_figures: List[str] = []
        for figure in figures:
            section_id = figure_assignments.get(figure.figure_id)
            if section_id is None and figure.page_label:
                section_id = self._pick_section_by_page(section_page_index, figure.page_label)
            if section_id is None and figure.page is not None:
                section_id = self._pick_section_by_page(section_page_index, str(figure.page))
            if section_id is None:
                missing_figures.append(figure.figure_id)

            rows.append(
                (
                    figure.figure_id,
                    section_id,
                    figure.image_path,
                    figure.page,
                    Json({"width": figure.width, "height": figure.height}),
                    figure.format,
                    figure.caption,
                    figure.embedding,
                )
            )

        cur.executemany(
            """
            INSERT INTO figures (
                figure_id,
                section_id,
                image_path,
                page_number,
                dimensions,
                format,
                caption,
                embedding
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (figure_id) DO UPDATE
                SET
                    section_id = EXCLUDED.section_id,
                    image_path = EXCLUDED.image_path,
                    page_number = EXCLUDED.page_number,
                    dimensions = EXCLUDED.dimensions,
                    format = EXCLUDED.format,
                    caption = EXCLUDED.caption,
                    embedding = EXCLUDED.embedding
            """,
            rows,
        )
        if missing_figures:
            logger.debug(
                "Unable to associate %d figures with sections (examples: %s)",
                len(missing_figures),
                ", ".join(missing_figures[:3]),
            )

    def _pick_section_by_page(self, page_index: Dict[str, List[int]], page_value: str) -> int | None:
        matches = page_index.get(page_value)
        if not matches:
            return None
        return matches[0]
