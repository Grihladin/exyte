"""LangGraph workflow assembly."""

from __future__ import annotations

from langgraph.graph import StateGraph

from rag.graph import nodes
from rag.graph.state import QueryState


def build_workflow():
    graph = StateGraph(QueryState)

    graph.add_node("analyze", nodes.analyze_query)
    graph.add_node("retrieve", nodes.retrieve_sections)
    graph.add_node("resolve_refs", nodes.resolve_references)
    graph.add_node("build_context", nodes.build_context)
    graph.add_node("answer", nodes.generate_answer)
    graph.add_node("format", nodes.format_response)

    graph.set_entry_point("analyze")
    graph.add_edge("analyze", "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        nodes.should_resolve_references,
        {
            "resolve": "resolve_refs",
            "skip": "build_context",
        },
    )
    graph.add_edge("resolve_refs", "build_context")
    graph.add_edge("build_context", "answer")
    graph.add_edge("answer", "format")
    graph.set_finish_point("format")

    return graph.compile()
