"""Run retrieval queries from the terminal for quick testing."""

from __future__ import annotations

import argparse
import logging
import textwrap
from typing import Sequence

from rag.config import settings
from rag.ingestion.embedder import OpenAIEmbedder
from rag.retrieval import ContextBuilder, HybridSearcher, ReferenceResolver, VectorSearcher

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute retrieval queries against the ingested database.")
    parser.add_argument("query", type=str, help="Natural language query to run.")
    parser.add_argument("--mode", choices=["vector", "hybrid"], default="hybrid", help="Search strategy.")
    parser.add_argument("--top-k", type=int, default=settings.top_k_sections, help="Number of sections to return.")
    parser.add_argument(
        "--allow-embed-fallback",
        action="store_true",
        help="Use deterministic embeddings if OPENAI_API_KEY is unavailable.",
    )
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="Expand retrieved sections with parents/children.",
    )
    parser.add_argument(
        "--show-references",
        action="store_true",
        help="Resolve referenced sections/tables/figures for the retrieved hits.",
    )
    parser.add_argument(
        "--max-snippet",
        type=int,
        default=300,
        help="Max number of characters to display per section snippet.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    embedder = OpenAIEmbedder(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        allow_fallback=args.allow_embed_fallback,
    )

    if args.mode == "hybrid":
        searcher = HybridSearcher(embedder)
    else:
        searcher = VectorSearcher(embedder)

    results = searcher.search(args.query, top_k=args.top_k)
    if not results:
        print("No sections found.")
        return 0

    print(f"\nTop {len(results)} sections for query: {args.query!r}\n")
    for idx, section in enumerate(results, 1):
        snippet = section.text.replace("\n", " ").strip()
        if len(snippet) > args.max_snippet:
            snippet = snippet[: args.max_snippet] + "..."
        print(f"{idx}. {section.section_number} – {section.title} (score={section.score:.3f})")
        print(textwrap.fill(snippet, width=100))
        print(f"   Chapter {section.chapter_number}: {section.chapter_title}")
        if section.page_number:
            print(f"   Page: {section.page_number}")
        print()

    if args.show_context:
        builder = ContextBuilder()
        context = builder.build(results)
        print(f"Context: {len(context['parents'])} parents, {len(context['children'])} children")

    if args.show_references:
        resolver = ReferenceResolver()
        bundle = resolver.resolve([section.id for section in results])
        print(
            f"References resolved: {len(bundle.sections)} sections, "
            f"{len(bundle.tables)} tables, {len(bundle.figures)} figures"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
