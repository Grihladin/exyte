"""Hybrid search that combines vector similarity and keyword matches."""

from __future__ import annotations

import logging
from typing import Dict, List

from rag.database.connection import get_sync_connection
from rag.ingestion.embedder import Embedder
from rag.retrieval.types import SectionResult
from rag.retrieval.vector_search import VectorSearcher
from rag.utils.ranking import reciprocal_rank_fusion

logger = logging.getLogger(__name__)


class HybridSearcher:
    """
    Hybrid search combining semantic vector search with keyword-based full-text search.

    This searcher implements a two-stage retrieval strategy:
    1. Vector search: Semantic similarity using embeddings
    2. Keyword search: Full-text search using PostgreSQL's tsquery
    3. Fusion: Combines results using Reciprocal Rank Fusion (RRF)

    The hybrid approach provides better recall and relevance by leveraging
    both semantic understanding and exact keyword matching.
    """

    def __init__(self, embedder: Embedder, *, fts_multiplier: int = 2) -> None:
        """
        Initialize hybrid searcher.

        Args:
            embedder: Embedder instance for vector search
            fts_multiplier: Multiplier for keyword search results (retrieves
                          more candidates from keyword search to improve recall)
        """
        self.vector_searcher = VectorSearcher(embedder)
        self.fts_multiplier = fts_multiplier

    def search(self, query: str, top_k: int = 5) -> List[SectionResult]:
        """
        Perform hybrid search combining vector and keyword approaches.

        Args:
            query: User query string
            top_k: Number of results to return

        Returns:
            List of SectionResult objects ranked by hybrid relevance score
        """
        if not query.strip():
            logger.warning("Empty query provided to hybrid search")
            return []

        try:
            # Perform both search strategies
            vector_results = self.vector_searcher.search(query, top_k=top_k)
            keyword_results = self._keyword_search(
                query, top_k=top_k * self.fts_multiplier
            )

            logger.debug(
                f"Hybrid search: {len(vector_results)} vector results, "
                f"{len(keyword_results)} keyword results"
            )

            # Handle edge cases
            if not keyword_results:
                return vector_results
            if not vector_results:
                return keyword_results[:top_k]

            # Combine results using RRF
            return self._fuse_results(vector_results, keyword_results, top_k)

        except Exception as e:
            logger.error(f"Error in hybrid search: {e}", exc_info=True)
            # Fallback to vector search only
            return self.vector_searcher.search(query, top_k=top_k)

    def _keyword_search(self, query: str, top_k: int) -> List[SectionResult]:
        """
        Perform PostgreSQL full-text search using tsquery.

        Args:
            query: Search query
            top_k: Maximum number of results

        Returns:
            List of matching sections ranked by ts_rank
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
                            ts_rank(s.full_text_search, plainto_tsquery('english', %s)) AS rank
                        FROM sections s
                        JOIN chapters c ON s.chapter_id = c.id
                        WHERE s.full_text_search @@ plainto_tsquery('english', %s)
                        ORDER BY rank DESC
                        LIMIT %s
                        """,
                        (query, query, top_k),
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
        except Exception as e:
            logger.error(f"Error in keyword search: {e}", exc_info=True)
            return []

    def _fuse_results(
        self,
        vector_results: List[SectionResult],
        keyword_results: List[SectionResult],
        top_k: int,
    ) -> List[SectionResult]:
        """
        Fuse vector and keyword results using Reciprocal Rank Fusion.

        RRF gives higher scores to documents that appear in multiple result lists
        and at higher ranks, providing a robust combination strategy.

        Args:
            vector_results: Results from vector search
            keyword_results: Results from keyword search
            top_k: Number of final results to return

        Returns:
            Fused and re-ranked results
        """
        # Build lookup map
        combined_map: Dict[int, SectionResult] = {}
        for result in vector_results + keyword_results:
            combined_map.setdefault(result.id, result)

        # Calculate fusion scores
        fusion_scores = reciprocal_rank_fusion(
            [
                [(result.id, result.score) for result in vector_results],
                [(result.id, result.score) for result in keyword_results],
            ]
        )

        # Rank and return
        ranked_ids = sorted(
            fusion_scores.items(), key=lambda item: item[1], reverse=True
        )

        return [combined_map[item_id] for item_id, _ in ranked_ids[:top_k]]
