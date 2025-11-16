"""Answer generation and response formatting nodes."""

from __future__ import annotations

import logging
import textwrap
from typing import Dict, Iterable

from rag.config import settings
from rag.graph.dependencies import get_chat_model
from rag.graph.state import QueryState
from rag.retrieval.types import SectionResult
from rag.utils.telemetry import log_event

logger = logging.getLogger(__name__)


def generate_answer(state: QueryState) -> QueryState:
    """Generate answer using LLM or extractive fallback."""
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
        except Exception as exc:
            logger.warning(
                "Chat model failed (%s); falling back to extractive answer.", exc
            )
            answer = _build_extractive_answer(sections)
    else:
        answer = _build_extractive_answer(sections)

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
    """Format final response with all context and metadata."""
    sections = state.get("retrieved_sections") or []
    references = state.get("references") or {}

    result = {
        "query": state["query"],
        "answer": state.get("answer", ""),
        "citations": state.get("citations", []),
        "metadata": state.get("metadata", {}),
        "sections": [_section_to_dict(section) for section in sections],
        "context": {
            "parents": [
                _section_to_dict(section)
                for section in state.get("parent_sections") or []
            ],
            "children": [
                _section_to_dict(section)
                for section in state.get("child_sections") or []
            ],
            "references": {
                "sections": [
                    _section_to_dict(section)
                    for section in references.get("sections", [])
                ],
                "tables": [
                    _table_to_dict(table) for table in references.get("tables", [])
                ],
                "figures": [
                    _figure_to_dict(figure) for figure in references.get("figures", [])
                ],
            },
        },
    }

    log_event(
        "format_response",
        {
            "citations": len(result.get("citations", [])),
            "sections": len(result.get("sections", [])),
        },
    )

    return {"result": result}


# Helper functions


def _build_extractive_answer(sections: Iterable[SectionResult]) -> str:
    """Build extractive answer from section snippets."""
    parts = []
    for section in sections:
        snippet = section.text.strip().replace("\n", " ")
        snippet = snippet[:400] + ("..." if len(snippet) > 400 else "")
        parts.append(f"{section.section_number} ({section.title}): {snippet}")
    return " ".join(parts)


def _section_to_dict(section: SectionResult) -> Dict:
    """Convert section result to dictionary."""
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


def _table_to_dict(table) -> Dict:
    """Convert table to dictionary."""
    return {
        "id": table.id,
        "table_id": table.table_id,
        "section_id": table.section_id,
        "headers": table.headers,
        "rows": table.rows,
        "page_number": table.page_number,
    }


def _figure_to_dict(figure) -> Dict:
    """Convert figure to dictionary."""
    return {
        "id": figure.id,
        "figure_id": figure.figure_id,
        "section_id": figure.section_id,
        "image_path": figure.image_path,
        "page_number": figure.page_number,
        "caption": figure.caption,
    }
