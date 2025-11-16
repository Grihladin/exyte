"""Embedding helpers used by the ingestion pipeline."""

from __future__ import annotations

import hashlib
import itertools
from typing import Dict, List, Protocol, Sequence

try:
    from langchain_openai import OpenAIEmbeddings
except Exception:  # pragma: no cover - optional dependency not installed during certain tests
    OpenAIEmbeddings = None  # type: ignore

try:
    import openai as _openai
except Exception:  # pragma: no cover - optional dependency not installed during certain tests
    _openai = None  # type: ignore


class Embedder(Protocol):
    """Protocol for embedding implementations."""

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Generate embeddings for the provided texts."""


class OpenAIEmbedder:
    """Embedding implementation backed by OpenAI with optional deterministic fallback."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        batch_size: int = 64,
        dimensions: int = 1536,
        allow_fallback: bool = False,
    ) -> None:
        self.model = model
        self.batch_size = batch_size
        self.dimensions = dimensions
        self.allow_fallback = allow_fallback
        self._client = None
        self._cache: Dict[str, List[float]] = {}

        if api_key and OpenAIEmbeddings is not None:
            self._client = OpenAIEmbeddings(model=model, openai_api_key=api_key)
        elif api_key and _openai is not None:
            # Use the low-level OpenAI SDK if langchain_openai isn't available.
            # This provides a lightweight fallback when the higher-level
            # langchain-openai package isn't installed.
            _openai.api_key = api_key
            self._client = _openai
        elif not allow_fallback:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured or langchain-openai is unavailable. "
                "Install dependencies (e.g., `uv sync` to install `langchain-openai`) or run ingestion with "
                "--skip-embeddings/--allow-embed-fallback. You can also `pip install openai` to use the OpenAI SDK fallback."
            )

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Batch embed all texts, reusing cached vectors where possible."""

        cleaned = [text.strip() for text in texts]
        if not cleaned:
            return []

        results: List[List[float]] = [list() for _ in cleaned]
        pending: List[tuple[int, str]] = []
        for idx, text in enumerate(cleaned):
            if not text:
                results[idx] = [0.0] * self.dimensions
                continue
            cached = self._cache.get(text)
            if cached is not None:
                results[idx] = cached
            else:
                pending.append((idx, text))

        if pending:
            if self._client is None:
                for idx, text in pending:
                    vector = self._fallback_embedding(text)
                    self._cache[text] = vector
                    results[idx] = vector
            else:
                for start in range(0, len(pending), self.batch_size):
                    batch = pending[start : start + self.batch_size]
                    batch_texts = [text for _, text in batch]
                    if hasattr(self._client, "embed_documents"):
                        # langchain-openai client
                        embeddings = self._client.embed_documents(batch_texts)
                    else:
                        # fallback to the OpenAI SDK
                        resp = self._client.Embeddings.create(model=self.model, input=batch_texts)
                        embeddings = [item["embedding"] for item in resp.data]
                    for (idx, text), vector in zip(batch, embeddings):
                        self._cache[text] = vector
                        results[idx] = vector

        return results

    def _fallback_embedding(self, text: str) -> List[float]:
        """Return a deterministic pseudo embedding (good for development/testing)."""

        if not text:
            return [0.0] * self.dimensions

        digest = hashlib.sha256(text.encode("utf-8")).digest()
        floats: List[float] = []
        for byte in itertools.islice(itertools.cycle(digest), self.dimensions):
            floats.append((byte / 255.0) * 2 - 1)
        return floats
