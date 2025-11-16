"""Validate that a parsed document was ingested correctly."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from psycopg import sql

from rag.database.connection import get_sync_connection
from rag.ingestion.loader import load_document
from rag.models import DocumentPayload, SectionPayload

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate database contents against a parser output file.")
    parser.add_argument("source", type=Path, help="Path to parser/output/parsed_document.json")
    parser.add_argument(
        "--document-id",
        type=int,
        default=None,
        help="Existing document ID to validate (defaults to matching title+version).",
    )
    parser.add_argument(
        "--sample-sections",
        type=int,
        default=5,
        help="Number of sections to sample for text/title validation.",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = parse_args()
    payload = load_document(args.source)
    expected_counts = _count_expected(payload)

    with get_sync_connection() as conn:
        document_id = resolve_document_id(conn, payload, args.document_id)
        db_counts = fetch_database_counts(conn, document_id, payload)
        count_mismatches = compare_counts(expected_counts, db_counts)

        sample_sections = list(payload.iter_sections())[: args.sample_sections]
        sample_failures = validate_section_samples(conn, document_id, sample_sections)

    if not count_mismatches and not sample_failures:
        logger.info("Validation successful for document id=%s (%s)", document_id, payload.title)
        return 0

    if count_mismatches:
        logger.error("Count mismatches detected:")
        for label, expected, actual in count_mismatches:
            logger.error("  %s: expected %s, found %s", label, expected, actual)
    if sample_failures:
        logger.error("Sample section mismatches detected:")
        for section_number, message in sample_failures:
            logger.error("  Section %s: %s", section_number, message)
    return 1


def _count_expected(payload: DocumentPayload) -> dict[str, int]:
    section_total = sum(len(ch.sections) for ch in payload.chapters)
    return {
        "chapters": len(payload.chapters),
        "sections": section_total,
        "tables": len(payload.tables),
        "figures": len(payload.figures),
    }


def resolve_document_id(conn, payload: DocumentPayload, requested_id: int | None) -> int:
    with conn.cursor() as cur:
        if requested_id is not None:
            cur.execute("SELECT id FROM documents WHERE id = %s", (requested_id,))
            row = cur.fetchone()
            if not row:
                raise SystemExit(f"Document id={requested_id} not found.")
            return requested_id

        cur.execute(
            """
            SELECT id
            FROM documents
            WHERE title = %s AND version = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (payload.title, payload.version),
        )
        row = cur.fetchone()
        if not row:
            raise SystemExit(
                f"No document found with title={payload.title!r} version={payload.version!r}. "
                "Did you run the ingestion script?"
            )
        return row[0]


def fetch_database_counts(conn, document_id: int, payload: DocumentPayload) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM chapters WHERE document_id = %s", (document_id,))
        chapter_ids = [row[0] for row in cur.fetchall()]

        cur.execute("SELECT COUNT(*) FROM chapters WHERE document_id = %s", (document_id,))
        chapters = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM sections WHERE chapter_id = ANY(%s)",
            (chapter_ids or [0],),
        )
        sections = cur.fetchone()[0]

        table_ids = [table.table_id for table in payload.tables]
        if table_ids:
            cur.execute(
                "SELECT COUNT(*) FROM tables WHERE table_id = ANY(%s)",
                (table_ids,),
            )
            tables = cur.fetchone()[0]
        else:
            tables = 0

        figure_ids = [figure.figure_id for figure in payload.figures]
        if figure_ids:
            cur.execute(
                "SELECT COUNT(*) FROM figures WHERE figure_id = ANY(%s)",
                (figure_ids,),
            )
            figures = cur.fetchone()[0]
        else:
            figures = 0

    return {
        "chapters": chapters,
        "sections": sections,
        "tables": tables,
        "figures": figures,
    }


def compare_counts(expected: dict[str, int], actual: dict[str, int]) -> List[Tuple[str, int, int]]:
    mismatches: List[Tuple[str, int, int]] = []
    for label, expected_value in expected.items():
        actual_value = actual.get(label, 0)
        if actual_value != expected_value:
            mismatches.append((label, expected_value, actual_value))
    return mismatches


def validate_section_samples(
    conn,
    document_id: int,
    sections: Sequence[SectionPayload],
) -> List[Tuple[str, str]]:
    if not sections:
        return []

    failures: List[Tuple[str, str]] = []
    with conn.cursor() as cur:
        for section in sections:
            cur.execute(
                """
                SELECT s.section_number, s.title, s.text
                FROM sections s
                JOIN chapters c ON s.chapter_id = c.id
                WHERE c.document_id = %s
                  AND (
                      s.section_number = %s
                      OR s.metadata->>'original_section_number' = %s
                  )
                ORDER BY COALESCE((s.metadata->>'duplicate_index')::int, 1), s.id
                LIMIT 1
                """,
                (document_id, section.section_number, section.section_number),
            )
            row = cur.fetchone()
            if not row:
                failures.append((section.section_number, "not found in database"))
                continue
            db_section_number, db_title, db_text = row
            if db_title.strip() != section.title.strip():
                failures.append(
                    (
                        section.section_number,
                        f"title mismatch (db={db_title!r}, expected={section.title!r})",
                    )
                )
            elif db_text.strip() != section.text.strip():
                failures.append(
                    (
                        section.section_number,
                        "text mismatch",
                    )
                )
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
