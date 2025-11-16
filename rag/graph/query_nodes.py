"""Query analysis and search strategy nodes."""

from __future__ import annotations

import logging

from rag.config import settings
from rag.graph.dependencies import get_hybrid_searcher, get_vector_searcher
from rag.graph.state import QueryState
from rag.utils.telemetry import log_event

logger = logging.getLogger(__name__)


def analyze_query(state: QueryState) -> QueryState:
    """
    Analyze query to determine type and search strategy.

    Query types:
    - comparison: Questions comparing multiple things
    - procedure: How-to questions needing step-by-step answers
    - factual: Direct factual questions
    """
    query = state["query"]
    lower = query.lower()

    # Determine query type
    if any(word in lower for word in ("difference", "compare", "vs", "versus")):
        query_type = "comparison"
    elif any(word in lower for word in ("how", "procedure", "steps", "process")):
        query_type = "procedure"
    else:
        query_type = "factual"

    # Determine search strategy
    options = state.get("options", {})
    search_strategy = options.get("search_type") or "hybrid"

    logger.info(f"Query analysis: type={query_type}, strategy={search_strategy}")

    new_state: QueryState = {
        **state,
        "query_type": query_type,
        "search_strategy": search_strategy,
    }

    log_event(
        "analyze_query", {"query_type": query_type, "search_strategy": search_strategy}
    )

    return new_state


def retrieve_sections(state: QueryState) -> QueryState:
    """Retrieve relevant sections using configured search strategy."""
    query = state["query"]
    options = state.get("options", {})
    top_k = options.get("max_sections") or settings.top_k_sections
    strategy = state.get("search_strategy", "hybrid")

    if strategy == "vector":
        searcher = get_vector_searcher()
    else:
        searcher = get_hybrid_searcher()

    results = searcher.search(query, top_k=top_k)
    logger.info("Retrieved %s sections using %s strategy", len(results), strategy)

    log_event(
        "retrieve_sections",
        {
            "count": len(results),
            "strategy": 0 if strategy == "vector" else 1,
            "top_k": top_k,
        },
    )

    return {
        **state,
        "retrieved_sections": results,
        "metadata": {
            **state.get("metadata", {}),
            "retrieval_count": len(results),
            "search_strategy": strategy,
        },
    }
