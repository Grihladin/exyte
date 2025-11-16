"""Vector similarity search powered by pgvector."""

from __future__ import annotations

import logging
from typing import List

from pgvector.psycopg import Vector

from rag.database.connection import get_sync_connection
from rag.ingestion.embedder import Embedder
from rag.retrieval.types import SectionResult

logger = logging.getLogger(__name__)


class VectorSearcher:
    """
    Semantic search using pgvector for efficient similarity queries.

    This searcher converts queries to embeddings and performs cosine similarity
    search against stored section embeddings using PostgreSQL's pgvector extension.
    """

    def __init__(self, embedder: Embedder) -> None:
        """
        Initialize vector searcher.

        Args:
            embedder: Embedder instance for generating query embeddings
        """
        self.embedder = embedder

    def search(self, query: str, top_k: int = 5) -> List[SectionResult]:
        """
        Perform semantic vector similarity search.

        Args:
            query: User query string
            top_k: Number of most similar sections to return

        Returns:
            List of SectionResult objects ranked by cosine similarity
        """
        if not query.strip():
            logger.warning("Empty query provided to vector search")
            return []

        try:
            # Generate query embedding
            embeddings = self.embedder.embed([query])
            if not embeddings:
                logger.error("Failed to generate embedding for query")
                return []

            query_embedding = Vector(embeddings[0])

            # Perform similarity search
            return self._similarity_search(query_embedding, top_k)

        except Exception as e:
            logger.error(f"Error in vector search: {e}", exc_info=True)
            return []

    def _similarity_search(
        self, query_embedding: Vector, top_k: int
    ) -> List[SectionResult]:
        """
        Execute similarity search against database.

        Uses cosine distance operator (<=> ) for efficient similarity search.
        Smaller distances indicate higher similarity; we convert to similarity
        score using (1 - distance).

        Args:
            query_embedding: Query vector
            top_k: Number of results to return

        Returns:
            List of matching sections with similarity scores
        """
        try:
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

            logger.debug(f"Vector search returned {len(rows)} results")

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
        except Exception as e:
            logger.error(f"Database error in similarity search: {e}", exc_info=True)
            return []
