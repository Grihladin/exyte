"""Hybrid search that combines vector similarity and keyword matches."""

from __future__ import annotations

from typing import Dict, List, Sequence

from rag.database.connection import get_sync_connection
from rag.ingestion.embedder import Embedder
from rag.retrieval.types import SectionResult
from rag.retrieval.vector_search import VectorSearcher
from rag.utils import reciprocal_rank_fusion


class HybridSearcher:
    def __init__(self, embedder: Embedder, *, fts_multiplier: int = 2) -> None:
        self.vector_searcher = VectorSearcher(embedder)
        self.fts_multiplier = fts_multiplier

    def search(self, query: str, top_k: int = 5) -> List[SectionResult]:
        if not query.strip():
            return []

        vector_results = self.vector_searcher.search(query, top_k=top_k)
        keyword_results = self._keyword_search(query, top_k=top_k * self.fts_multiplier)

        if not keyword_results:
            return vector_results
        if not vector_results:
            return keyword_results[:top_k]

        combined_map: Dict[int, SectionResult] = {}
        for result in vector_results + keyword_results:
            combined_map.setdefault(result.id, result)

        fusion_scores = reciprocal_rank_fusion(
            [
                [(result.id, result.score) for result in vector_results],
                [(result.id, result.score) for result in keyword_results],
            ]
        )

        ranked_ids = sorted(fusion_scores.items(), key=lambda item: item[1], reverse=True)
        return [combined_map[item_id] for item_id, _ in ranked_ids[:top_k]]

    def _keyword_search(self, query: str, top_k: int) -> List[SectionResult]:
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
