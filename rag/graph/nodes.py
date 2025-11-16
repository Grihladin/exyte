"""LangGraph node implementations."""

from __future__ import annotations

import logging
import textwrap
from functools import lru_cache
from typing import Dict, Iterable, List

from langchain_openai import ChatOpenAI

from rag.config import settings
from rag.graph.state import QueryOptions, QueryState
from rag.ingestion.embedder import OpenAIEmbedder
from rag.retrieval import ContextBuilder, HybridSearcher, ReferenceResolver, VectorSearcher
from rag.retrieval.types import ReferenceBundle, SectionResult
from rag.utils.telemetry import log_event

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Dependency singletons
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def get_embedder() -> OpenAIEmbedder:
    return OpenAIEmbedder(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        allow_fallback=not bool(settings.openai_api_key),
    )


@lru_cache(maxsize=1)
def get_vector_searcher() -> VectorSearcher:
    return VectorSearcher(get_embedder())


@lru_cache(maxsize=1)
def get_hybrid_searcher() -> HybridSearcher:
    return HybridSearcher(get_embedder())


@lru_cache(maxsize=1)
def get_context_builder() -> ContextBuilder:
    return ContextBuilder()


@lru_cache(maxsize=1)
def get_reference_resolver() -> ReferenceResolver:
    return ReferenceResolver()


@lru_cache(maxsize=1)
def get_chat_model() -> ChatOpenAI | None:
    if not settings.openai_api_key:
        return None
    try:
        return ChatOpenAI(
            model=settings.chat_model,
            temperature=settings.temperature,
            openai_api_key=settings.openai_api_key,
        )
    except Exception as exc:  # pragma: no cover - depends on LLM availability
        logger.warning("Failed to initialize ChatOpenAI: %s", exc)
        return None


# --------------------------------------------------------------------------- #
# Node implementations
# --------------------------------------------------------------------------- #
def analyze_query(state: QueryState) -> QueryState:
    query = state["query"]
    lower = query.lower()
    if any(word in lower for word in ("difference", "compare", "vs", "versus")):
        query_type = "comparison"
    elif any(word in lower for word in ("how", "procedure", "steps")):
        query_type = "procedure"
    else:
        query_type = "factual"

    options = state.get("options", {})
    search_strategy = options.get("search_type") or "hybrid"

    new_state: QueryState = {
        **state,
        "query_type": query_type,
        "search_strategy": search_strategy,
    }
    log_event("analyze_query", {"query_type": query_type, "search_strategy": search_strategy})
    return new_state


def retrieve_sections(state: QueryState) -> QueryState:
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
        {"count": len(results), "strategy": 0 if strategy == "vector" else 1, "top_k": top_k},
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


def resolve_references(state: QueryState) -> QueryState:
    sections = state.get("retrieved_sections") or []
    if not sections:
        return state
    resolver = get_reference_resolver()
    bundle = resolver.resolve([section.id for section in sections])
    references = {
        "sections": bundle.sections,
        "tables": bundle.tables,
        "figures": bundle.figures,
    }
    logger.info(
        "Resolved references: %s sections, %s tables, %s figures",
        len(bundle.sections),
        len(bundle.tables),
        len(bundle.figures),
    )
    log_event(
        "resolve_references",
        {"section_refs": len(bundle.sections), "table_refs": len(bundle.tables), "figure_refs": len(bundle.figures)},
    )
    return {**state, "references": references}


def build_context(state: QueryState) -> QueryState:
    sections = state.get("retrieved_sections") or []
    if not sections:
        return state
    builder = get_context_builder()
    bundle = builder.build(sections)
    new_state = {
        **state,
        "context_sections": bundle["sections"],
        "parent_sections": bundle["parents"],
        "child_sections": bundle["children"],
    }
    log_event(
        "build_context",
        {
            "base_sections": len(bundle["sections"]),
            "parent_sections": len(bundle["parents"]),
            "child_sections": len(bundle["children"]),
        },
    )
    return new_state


def generate_answer(state: QueryState) -> QueryState:
    sections = state.get("context_sections") or state.get("retrieved_sections") or []
    if not sections:
        return {**state, "answer": "No relevant sections were found.", "citations": []}

    context_chunks = []
    citations = []
    for section in sections:
        chunk = f"Section {section.section_number} ({section.title})\n{section.text}"
        context_chunks.append(chunk)
        citations.append(
            {
                "section_number": section.section_number,
                "title": section.title,
                "chapter": section.chapter_number,
                "page": section.page_number,
            }
        )
    context_text = "\n\n".join(context_chunks)

    model = get_chat_model()
    if model:
        prompt = textwrap.dedent(
            f"""
            You are a building code expert. Answer the question using the provided context.

            Question: {state['query']}

            Context:
            {context_text}

            Provide a concise answer and mention relevant section numbers.
            """
        ).strip()
        try:
            response = model.invoke(prompt)
            answer = response.content if hasattr(response, "content") else str(response)
        except Exception as exc:  # pragma: no cover - depends on LLM availability
            logger.warning("Chat model failed (%s); falling back to extractive answer.", exc)
            answer = build_extractive_answer(sections)
    else:
        answer = build_extractive_answer(sections)
    log_event(
        "generate_answer",
        {"context_sections": len(sections), "citations": len(citations), "used_llm": 1 if model else 0},
    )
    return {
        **state,
        "answer": answer.strip(),
        "citations": citations[: settings.top_k_sections],
        "context_text": context_text,
    }


def format_response(state: QueryState) -> QueryState:
    sections = state.get("retrieved_sections") or []
    references = state.get("references") or {}
    result = {
        "query": state["query"],
        "answer": state.get("answer", ""),
        "citations": state.get("citations", []),
        "metadata": state.get("metadata", {}),
        "sections": [section_to_dict(section) for section in sections],
        "context": {
            "parents": [section_to_dict(section) for section in state.get("parent_sections") or []],
            "children": [section_to_dict(section) for section in state.get("child_sections") or []],
            "references": {
                "sections": [section_to_dict(section) for section in references.get("sections", [])],
                "tables": [table_to_dict(table) for table in references.get("tables", [])],
                "figures": [figure_to_dict(figure) for figure in references.get("figures", [])],
            },
        },
    }
    log_event(
        "format_response",
        {"citations": len(result.get("citations", [])), "sections": len(result.get("sections", []))},
    )
    return {"result": result}


# --------------------------------------------------------------------------- #
# Conditional routing helpers
# --------------------------------------------------------------------------- #
def should_resolve_references(state: QueryState) -> str:
    options = state.get("options", {})
    include_tables = options.get("include_tables", True)
    include_figures = options.get("include_figures", True)
    if include_tables or include_figures:
        return "resolve"
    return "skip"


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #
def build_extractive_answer(sections: Iterable[SectionResult]) -> str:
    parts = []
    for section in sections:
        snippet = section.text.strip().replace("\n", " ")
        snippet = snippet[:400] + ("..." if len(snippet) > 400 else "")
        parts.append(f"{section.section_number} ({section.title}): {snippet}")
    return " ".join(parts)


def section_to_dict(section: SectionResult) -> Dict:
    return {
        "id": section.id,
        "section_number": section.section_number,
        "title": section.title,
        "text": section.text,
        "chapter_id": section.chapter_id,
        "chapter_number": section.chapter_number,
        "chapter_title": section.chapter_title,
        "depth": section.depth,
        "parent_section_id": section.parent_section_id,
        "page_number": section.page_number,
        "metadata": section.metadata,
        "score": section.score,
    }


def table_to_dict(table) -> Dict:
    return {
        "id": table.id,
        "table_id": table.table_id,
        "section_id": table.section_id,
        "headers": table.headers,
        "rows": table.rows,
        "page_number": table.page_number,
    }


def figure_to_dict(figure) -> Dict:
    return {
        "id": figure.id,
        "figure_id": figure.figure_id,
        "section_id": figure.section_id,
        "image_path": figure.image_path,
        "page_number": figure.page_number,
        "caption": figure.caption,
    }
