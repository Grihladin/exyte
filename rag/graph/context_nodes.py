"""Context building and reference resolution nodes."""

from __future__ import annotations

import logging

from rag.graph.dependencies import get_context_builder, get_reference_resolver
from rag.graph.state import QueryState
from rag.utils.telemetry import log_event

logger = logging.getLogger(__name__)


def resolve_references(state: QueryState) -> QueryState:
    """Resolve tables and figures referenced by retrieved sections."""
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
    """Build hierarchical context from retrieved sections."""
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


def should_resolve_references(state: QueryState) -> str:
    """Determine if references should be resolved based on options."""
    options = state.get("options", {})
    include_tables = options.get("include_tables", True)
    include_figures = options.get("include_figures", True)

    if include_tables or include_figures:
        return "resolve"
    return "skip"
