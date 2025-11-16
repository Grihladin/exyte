"""Run the LangGraph workflow for a single query."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from rag.graph import build_workflow

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute the LangGraph retrieval + answer workflow.")
    parser.add_argument("query", type=str, help="User query to process.")
    parser.add_argument("--max-sections", type=int, default=5, help="Maximum sections to retrieve.")
    parser.add_argument(
        "--search-type",
        choices=["hybrid", "vector"],
        default="hybrid",
        help="Search strategy.",
    )
    parser.add_argument("--no-tables", action="store_true", help="Do not resolve table references.")
    parser.add_argument("--no-figures", action="store_true", help="Do not resolve figure references.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workflow = build_workflow()
    options = {
        "max_sections": args.max_sections,
        "search_type": args.search_type,
        "include_tables": not args.no_tables,
        "include_figures": not args.no_figures,
    }
    output = workflow.invoke({"query": args.query, "options": options})
    result = output.get("result", {})

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Query: {result.get('query')}")
        print(f"Answer:\n{result.get('answer')}\n")
        if result.get("citations"):
            print("Citations:")
            for citation in result["citations"]:
                print(
                    f" - Section {citation.get('section_number')} ({citation.get('title')}) "
                    f"[Chapter {citation.get('chapter')}, Page {citation.get('page')}]"
                )
        print()
        print(f"Sections returned: {len(result.get('sections', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
