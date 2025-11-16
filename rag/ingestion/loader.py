"""Utilities for loading parser output into structured models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from rag.models import DocumentPayload


def load_document(path: str | Path) -> DocumentPayload:
    """Load a parsed document JSON file into a :class:`DocumentPayload`."""

    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return load_document_from_dict(data, source_path=str(file_path))


def load_document_from_dict(data: Mapping[str, Any], *, source_path: str | None = None) -> DocumentPayload:
    """Convert a mapping (already loaded JSON) into a payload."""

    return DocumentPayload.from_raw(data, source_path=source_path)
