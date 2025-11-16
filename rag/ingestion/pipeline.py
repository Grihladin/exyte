"""High-level ingestion pipeline orchestration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, List, Mapping, Sequence

from rag.config import settings
from rag.ingestion.embedder import Embedder, OpenAIEmbedder
from rag.ingestion.loader import load_document, load_document_from_dict
from rag.ingestion.writer import DatabaseWriter
from rag.models import DocumentPayload, FigurePayload, SectionPayload, TablePayload

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Coordinates document loading, embedding generation, and persistence."""

    def __init__(
        self,
        *,
        embedder: Embedder | None = None,
        enable_embeddings: bool = True,
        allow_embedding_fallback: bool = False,
        embedding_batch_size: int = 64,
    ) -> None:
        self.enable_embeddings = enable_embeddings
        self.embedder = embedder
        if self.embedder is None and enable_embeddings:
            self.embedder = OpenAIEmbedder(
                model=settings.embedding_model,
                api_key=settings.openai_api_key,
                batch_size=embedding_batch_size,
                allow_fallback=allow_embedding_fallback,
            )
        self.writer = DatabaseWriter()

    def ingest(self, source: str | Path | dict) -> int:
        """Run the pipeline using a file path or an already loaded dictionary."""

        if isinstance(source, (str, Path)):
            document = load_document(source)
        elif isinstance(source, Mapping):
            document = load_document_from_dict(source, source_path=None)
        else:
            raise TypeError(f"Unsupported source type: {type(source)!r}")

        if self.enable_embeddings and self.embedder:
            self._apply_embeddings(document)
        else:
            logger.info("Skipping embedding generation for %s", document.title)

        document_id = self.writer.write(document)
        logger.info("Ingested document %s (id=%s)", document.title, document_id)
        return document_id

    # ------------------------------------------------------------------ #
    # Embedding helpers
    # ------------------------------------------------------------------ #
    def _apply_embeddings(self, document: DocumentPayload) -> None:
        sections = list(document.iter_sections())
        self._assign_embeddings(sections, lambda section: section.embedding_text())
        self._assign_embeddings(document.tables, lambda table: table.embedding_text())
        self._assign_embeddings(document.figures, lambda figure: figure.embedding_text())

    def _assign_embeddings(
        self,
        items: Sequence[Any],
        text_getter: Callable[[Any], str],
    ) -> None:
        if not items or not self.embedder:
            return

        texts: List[str] = []
        non_empty_indices: List[int] = []
        for index, item in enumerate(items):
            text = text_getter(item).strip()
            if not text:
                continue
            texts.append(text)
            non_empty_indices.append(index)

        if not texts:
            return

        embeddings = self.embedder.embed(texts)
        if len(embeddings) != len(non_empty_indices):
            raise RuntimeError("Embedding count mismatch")

        for idx, vector in zip(non_empty_indices, embeddings):
            items[idx].embedding = vector
