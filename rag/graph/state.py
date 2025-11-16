"""State definitions for the LangGraph workflow."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from rag.retrieval.types import SectionResult, TableResult, FigureResult


class QueryOptions(TypedDict, total=False):
    max_sections: int
    include_tables: bool
    include_figures: bool
    search_type: str


class QueryState(TypedDict, total=False):
    query: str
    options: QueryOptions
    query_type: str
    search_strategy: str
    retrieved_sections: List[SectionResult]
    context_sections: List[SectionResult]
    parent_sections: List[SectionResult]
    child_sections: List[SectionResult]
    references: Dict[str, List]
    answer: str
    citations: List[Dict[str, Any]]
    context_text: str
    metadata: Dict[str, Any]
    result: Dict[str, Any]
