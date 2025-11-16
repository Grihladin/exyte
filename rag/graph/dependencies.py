"""Cached dependency singletons for RAG workflow components."""

from __future__ import annotations

import logging
from functools import lru_cache

from langchain_openai import ChatOpenAI

from rag.config import settings
from rag.ingestion.embedder import OpenAIEmbedder
from rag.retrieval import (
    ContextBuilder,
    HybridSearcher,
    ReferenceResolver,
    VectorSearcher,
)

logger = logging.getLogger(__name__)


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
