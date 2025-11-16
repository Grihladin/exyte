"""Section detail endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from rag.api.models import SectionDetailModel, SectionSummaryModel
from rag.database.connection import get_sync_connection
from rag.retrieval.reference_resolver import ReferenceResolver

router = APIRouter(prefix="/sections", tags=["sections"])
resolver = ReferenceResolver()


@router.get("/{section_number}", response_model=SectionDetailModel)
async def get_section(section_number: str) -> SectionDetailModel:
    with get_sync_connection() as conn:
        section_row = _fetch_section_row(conn, section_number)
        if not section_row:
            raise HTTPException(status_code=404, detail="Section not found.")

        parent = _fetch_section_by_id(conn, section_row["parent_section_id"]) if section_row["parent_section_id"] else None
        children = _fetch_children(conn, section_row["id"])

    section_model = _row_to_model(section_row)
    parent_model = _row_to_model(parent) if parent else None
    children_models = [_row_to_model(child) for child in children]

    references = resolver.resolve([section_model.id])
    references_payload = {
        "sections": [section.section_number for section in references.sections],
        "tables": [table.table_id for table in references.tables],
        "figures": [figure.figure_id for figure in references.figures],
    }

    return SectionDetailModel(
        section=section_model,
        parent=parent_model,
        children=children_models,
        references=references_payload,
    )


def _fetch_section_row(conn, section_number: str):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                s.id,
                s.section_number,
                s.title,
                s.text,
                s.metadata,
                s.page_number,
                s.parent_section_id,
                c.chapter_number,
                c.title AS chapter_title
            FROM sections s
            JOIN chapters c ON s.chapter_id = c.id
            WHERE s.section_number = %s
            LIMIT 1
            """,
            (section_number,),
        )
        row = cur.fetchone()
        if row:
            return row
        cur.execute(
            """
            SELECT
                s.id,
                s.section_number,
                s.title,
                s.text,
                s.metadata,
                s.page_number,
                s.parent_section_id,
                c.chapter_number,
                c.title AS chapter_title
            FROM sections s
            JOIN chapters c ON s.chapter_id = c.id
            WHERE s.metadata->>'original_section_number' = %s
            ORDER BY s.id
            LIMIT 1
            """,
            (section_number,),
        )
        return cur.fetchone()


def _fetch_section_by_id(conn, section_id: int | None):
    if section_id is None:
        return None
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                s.id,
                s.section_number,
                s.title,
                s.text,
                s.metadata,
                s.page_number,
                s.parent_section_id,
                c.chapter_number,
                c.title AS chapter_title
            FROM sections s
            JOIN chapters c ON s.chapter_id = c.id
            WHERE s.id = %s
            """,
            (section_id,),
        )
        return cur.fetchone()


def _fetch_children(conn, section_id: int):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                s.id,
                s.section_number,
                s.title,
                s.text,
                s.metadata,
                s.page_number,
                s.parent_section_id,
                c.chapter_number,
                c.title AS chapter_title
            FROM sections s
            JOIN chapters c ON s.chapter_id = c.id
            WHERE s.parent_section_id = %s
            ORDER BY s.section_number
            """,
            (section_id,),
        )
        return cur.fetchall()


def _row_to_model(row) -> SectionSummaryModel:
    return SectionSummaryModel(
        id=row["id"],
        section_number=row["section_number"],
        title=row["title"],
        text=row["text"],
        chapter_number=row["chapter_number"],
        chapter_title=row["chapter_title"],
        parent_section_id=row["parent_section_id"],
        page_number=row["page_number"],
        metadata=row.get("metadata") or {},
    )


try:
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - psycopg v3 required
    from psycopg.rows import tuple_row as dict_row
