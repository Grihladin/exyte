"""Typed result objects for retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SectionResult:
    id: int
    section_number: str
    title: str
    text: str
    score: float
    chapter_id: int
    chapter_number: Optional[int]
    chapter_title: Optional[str]
    depth: int
    parent_section_id: Optional[int]
    page_number: Optional[str]
    metadata: Dict[str, Any]

    def short_label(self) -> str:
        return f"{self.section_number} – {self.title}"


@dataclass(frozen=True)
class TableResult:
    id: int
    table_id: str
    table_name: str | None
    section_id: Optional[int]
    markdown: Optional[str]
    page_number: Optional[int]


@dataclass(frozen=True)
class FigureResult:
    id: int
    figure_id: str
    section_id: Optional[int]
    image_path: Optional[str]
    page_number: Optional[int]
    caption: Optional[str]


@dataclass(frozen=True)
class ReferenceBundle:
    sections: List[SectionResult]
    tables: List[TableResult]
    figures: List[FigureResult]
