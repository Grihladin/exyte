"""LangGraph node implementations for RAG workflow."""

from __future__ import annotations

import logging
import textwrap
from functools import lru_cache
from typing import Dict, Iterable, List

from langchain_openai import ChatOpenAI

from rag.config import settings
from rag.graph.state import QueryState
from rag.ingestion.embedder import OpenAIEmbedder
from rag.retrieval import (
    ContextBuilder,
    HybridSearcher,
    ReferenceResolver,
    VectorSearcher,
)
from rag.retrieval.types import SectionResult
from rag.utils.telemetry import log_event

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Dependency singletons (cached for performance)
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def get_embedder() -> OpenAIEmbedder:
    """Get cached embedder instance."""
    return OpenAIEmbedder(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        allow_fallback=not settings.is_openai_configured,
    )


@lru_cache(maxsize=1)
def get_vector_searcher() -> VectorSearcher:
    """Get cached vector searcher instance."""
    return VectorSearcher(get_embedder())


@lru_cache(maxsize=1)
def get_hybrid_searcher() -> HybridSearcher:
    """Get cached hybrid searcher instance."""
    return HybridSearcher(get_embedder())


@lru_cache(maxsize=1)
def get_context_builder() -> ContextBuilder:
    """Get cached context builder instance."""
    return ContextBuilder()


@lru_cache(maxsize=1)
def get_reference_resolver() -> ReferenceResolver:
    """Get cached reference resolver instance."""
    return ReferenceResolver()


@lru_cache(maxsize=1)
def get_chat_model() -> ChatOpenAI | None:
    """Get cached LLM instance, or None if not configured."""
    if not settings.is_openai_configured:
        logger.warning("OpenAI API key not configured - using fallback answers")
        return None

    try:
        return ChatOpenAI(
            model=settings.chat_model,
            temperature=settings.temperature,
            openai_api_key=settings.openai_api_key,
        )
    except Exception as exc:
        logger.error(f"Failed to initialize ChatOpenAI: {exc}", exc_info=True)
        return None


# --------------------------------------------------------------------------- #
# Node implementations
# --------------------------------------------------------------------------- #


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
        {
            "section_refs": len(bundle.sections),
            "table_refs": len(bundle.tables),
            "figure_refs": len(bundle.figures),
        },
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
        fallback_answer = (
            "I apologize, but I couldn't find any relevant information in the building code database "
            "to answer your question. This might be because:\n"
            "1. The database hasn't been populated with building code documents yet\n"
            "2. Your question is outside the scope of the available building codes\n"
            "3. The search terms didn't match any indexed sections\n\n"
            "Please try rephrasing your question or contact the administrator if the database needs to be populated."
        )
        return {**state, "answer": fallback_answer, "citations": []}

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
            logger.warning(
                "Chat model failed (%s); falling back to extractive answer.", exc
            )
            answer = build_extractive_answer(sections)
    else:
        answer = build_extractive_answer(sections)
    log_event(
        "generate_answer",
        {
            "context_sections": len(sections),
            "citations": len(citations),
            "used_llm": 1 if model else 0,
        },
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
    citations = state.get("citations", [])
    answer = state.get("answer", "")

    # Build Markdown response
    md_parts = [answer]

    # Check if we have any references/citations
    ref_sections = references.get("sections", [])
    ref_tables = references.get("tables", [])
    ref_figures = references.get("figures", [])

    if citations or ref_sections or ref_tables or ref_figures:
        md_parts.append("### References")

        # 1. Sections
        # Combine citations and referenced sections
        seen_sections = set()
        section_lines = []

        # Add citations first
        for cit in citations:
            sec_num = cit.get("section_number")
            if sec_num and sec_num not in seen_sections:
                seen_sections.add(sec_num)
                title = cit.get("title", "")
                section_lines.append(f"- **Section {sec_num}**: {title}")

        # Add referenced sections
        for sec in ref_sections:
            if sec.section_number not in seen_sections:
                seen_sections.add(sec.section_number)
                section_lines.append(f"- **Section {sec.section_number}**: {sec.title}")

        if section_lines:
            md_parts.append("#### Sections\n" + "\n".join(section_lines))

        # 2. Tables
        if ref_tables:
            table_lines = [f"- **Table {table.table_id}**: {table.table_name}" for table in ref_tables]
            md_parts.append("#### Tables\n" + "\n".join(table_lines))

        # 3. Figures
        if ref_figures:
            fig_lines = [f"- **Figure {fig.figure_id}**: {fig.caption}" for fig in ref_figures]
            md_parts.append("#### Figures\n" + "\n".join(fig_lines))

    formatted_answer = "\n\n".join(md_parts)

    result = {
        "query": state["query"],
        "answer": formatted_answer,
        "citations": [],  # Clear citations to prevent double formatting in API
        "metadata": state.get("metadata", {}),
        "sections": [section_to_dict(section) for section in sections],
        "context": {
            "parents": [
                section_to_dict(section)
                for section in state.get("parent_sections") or []
            ],
            "children": [
                section_to_dict(section)
                for section in state.get("child_sections") or []
            ],
            "references": {
                "sections": [
                    section_to_dict(section)
                    for section in references.get("sections", [])
                ],
                "tables": [
                    table_to_dict(table) for table in references.get("tables", [])
                ],
                "figures": [
                    figure_to_dict(figure) for figure in references.get("figures", [])
                ],
            },
        },
    }
    log_event(
        "format_response",
        {
            "citations": len(citations),
            "sections": len(result.get("sections", [])),
        },
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
        "table_name": table.table_name,
        "section_id": table.section_id,
        "markdown": table.markdown,
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
