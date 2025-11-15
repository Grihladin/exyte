"""Data models for PDF document parsing."""

from .document import (
    Document,
    Chapter,
    Section,
    NumberedItem,
    Metadata,
)
from .references import (
    Reference,
    InternalSectionReference,
    TableReference,
    FigureReference,
    ExternalDocumentReference,
    References,
    TableData,
    Position,
)

__all__ = [
    "Document",
    "Chapter",
    "Section",
    "NumberedItem",
    "Metadata",
    "Reference",
    "InternalSectionReference",
    "TableReference",
    "FigureReference",
    "ExternalDocumentReference",
    "References",
    "TableData",
    "Position",
]
