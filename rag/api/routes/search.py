"""Search endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from rag.api.models import SearchResponse, SearchResultModel
from rag.graph.nodes import get_hybrid_searcher, get_vector_searcher

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_endpoint(
    q: str = Query(..., description="Query string"),
    limit: int = Query(5, ge=1, le=50),
    search_type: str = Query("hybrid", regex="^(hybrid|vector)$"),
) -> SearchResponse:
    if not q.strip():
        raise HTTPException(status_code=400, detail="Parameter 'q' cannot be empty.")

    if search_type == "vector":
        searcher = get_vector_searcher()
    else:
        searcher = get_hybrid_searcher()

    results = searcher.search(q, top_k=limit)
    payload = [
        SearchResultModel(
            section_number=section.section_number,
            title=section.title,
            text=section.text,
            chapter_number=section.chapter_number,
            chapter_title=section.chapter_title,
            page_number=section.page_number,
            score=section.score,
        )
        for section in results
    ]
    return SearchResponse(query=q, results=payload, count=len(payload))
