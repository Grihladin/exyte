"""Vector similarity search powered by pgvector."""

from __future__ import annotations

from typing import List, Sequence

from pgvector.psycopg import Vector

from rag.database.connection import get_sync_connection
from rag.ingestion.embedder import Embedder
from rag.retrieval.types import SectionResult


class VectorSearcher:
    """Perform semantic search using section embeddings."""

    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder

    def search(self, query: str, top_k: int = 5) -> List[SectionResult]:
        if not query.strip():
            return []
        embeddings = self.embedder.embed([query])
        if not embeddings:
            return []
        query_embedding = Vector(embeddings[0])
        with get_sync_connection() as conn:
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
                        c.title AS chapter_title,
                        1 - (s.embedding <=> %s) AS similarity
                    FROM sections s
                    JOIN chapters c ON s.chapter_id = c.id
                    WHERE s.embedding IS NOT NULL
                    ORDER BY s.embedding <=> %s
                    LIMIT %s
                    """,
                    (query_embedding, query_embedding, top_k),
                )
                rows = cur.fetchall()

        return [
            SectionResult(
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
                score=float(row[11]),
            )
            for row in rows
        ]
