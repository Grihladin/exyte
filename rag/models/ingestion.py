"""Pydantic models that describe parser output for ingestion."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterator, List, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

ReferenceType = Literal["section", "table", "figure", "external", "unknown"]


def guess_section_number(identifier: str) -> str | None:
    """Best-effort extraction of a section number from identifiers like ``307.1(1)``."""

    match = re.match(r"^([0-9]+(?:\.[0-9A-Za-z]+)*)", identifier or "")
    if match:
        return match.group(1)
    return None


class NumberedItemPayload(BaseModel):
    """Represents a numbered list item present within a section."""

    model_config = ConfigDict(frozen=True)

    number: int
    text: str


class ReferencePayload(BaseModel):
    """Normalized representation of a reference mention inside a section."""

    model_config = ConfigDict(frozen=True)

    reference_type: ReferenceType
    reference_text: str
    position_start: int | None = None
    position_end: int | None = None


class SectionPayload(BaseModel):
    """Single section of a chapter."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    section_number: str
    title: str
    text: str
    depth: int
    prefix: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    numbered_items: List[NumberedItemPayload] = Field(default_factory=list)
    references: List[ReferencePayload] = Field(default_factory=list)
    page_number: str | None = None
    embedding: List[float] | None = None

    def embedding_text(self) -> str:
        """Return a deterministic text block for embedding generation."""

        header_parts = [self.section_number, self.title]
        header = " - ".join([part for part in header_parts if part])
        return f"{header}\n{self.text}".strip()


class ChapterPayload(BaseModel):
    """Chapter plus its ordered sections."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    chapter_number: int
    title: str
    user_notes: str | None = None
    sections: List[SectionPayload] = Field(default_factory=list)


class TablePayload(BaseModel):
    """Tabular data extracted from the source PDF."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    table_id: str
    table_name: str | None = None
    markdown: str | None = Field(default=None, description="Markdown representation of the table")
    page_number: int | None = None
    accuracy: float | None = None
    section_number_hint: str | None = None
    embedding: List[float] | None = None

    def embedding_text(self) -> str:
        """Return a condensed textual representation of the table."""

        title = self.table_name
        if self.markdown:
            return f"{title}\n{self.markdown}".strip()
        return title


class FigurePayload(BaseModel):
    """Metadata describing an extracted figure."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    figure_id: str
    page: int | None = None
    page_label: str | None = None
    image_path: str | None = None
    width: int | None = None
    height: int | None = None
    format: str | None = None
    caption: str | None = None
    embedding: List[float] | None = None

    def embedding_text(self) -> str:
        """Return a minimal textual payload for embeddings."""

        parts = [
            f"Figure {self.figure_id}",
            f"Page {self.page_label or self.page}" if (self.page_label or self.page) else "",
            self.caption or "",
        ]
        return "\n".join([part for part in parts if part]).strip()


class DocumentPayload(BaseModel):
    """Normalized document with chapters, sections, tables, and figures."""

    title: str
    version: str
    chapters: List[ChapterPayload] = Field(default_factory=list)
    tables: List[TablePayload] = Field(default_factory=list)
    figures: List[FigurePayload] = Field(default_factory=list)
    source_path: str | None = None

    @classmethod
    def from_raw(
        cls,
        data: Mapping[str, Any],
        *,
        source_path: str | None = None,
    ) -> "DocumentPayload":
        """Build a payload from raw parser output."""

        chapters = [_build_chapter(chapter) for chapter in data.get("chapters", [])]

        tables = []
        for table_id, table_data in (data.get("tables") or {}).items():
            tables.append(
                TablePayload(
                    table_id=table_id,
                    table_name=table_data.get("table_name"),
                    markdown=table_data.get("markdown"),
                    page_number=table_data.get("page"),
                    accuracy=table_data.get("accuracy"),
                    section_number_hint=table_data.get("section_number") or guess_section_number(table_id),
                )
            )

        figures = []
        for _, figure in (data.get("figures") or {}).items():
            figures.append(
                FigurePayload(
                    figure_id=figure.get("figure_id") or figure.get("id") or "",
                    page=figure.get("page"),
                    page_label=str(figure.get("page_label")) if figure.get("page_label") is not None else None,
                    image_path=figure.get("image_path"),
                    width=figure.get("width"),
                    height=figure.get("height"),
                    format=figure.get("format"),
                    caption=figure.get("caption"),
                )
            )

        payload = cls(
            title=data.get("title", "Untitled Document"),
            version=data.get("version", "unknown"),
            chapters=chapters,
            tables=tables,
            figures=figures,
            source_path=source_path,
        )
        return payload

    def iter_sections(self) -> Iterator[SectionPayload]:
        """Yield every section in chapter order."""

        for chapter in self.chapters:
            for section in chapter.sections:
                yield section


def _build_chapter(raw_chapter: Mapping[str, Any]) -> ChapterPayload:
    sections = [_build_section(section) for section in raw_chapter.get("sections", [])]
    return ChapterPayload(
        chapter_number=int(raw_chapter.get("chapter_number", 0)),
        title=raw_chapter.get("title") or "",
        user_notes=raw_chapter.get("user_notes"),
        sections=sections,
    )


def _build_section(raw_section: Mapping[str, Any]) -> SectionPayload:
    metadata = dict(raw_section.get("metadata") or {})
    page_number = metadata.get("page_number")
    if page_number is not None:
        page_number = str(page_number)

    numbered_items = [
        NumberedItemPayload(number=item.get("number"), text=item.get("text") or "")
        for item in raw_section.get("numbered_items", [])
    ]

    references = _build_references(raw_section.get("references") or {})

    return SectionPayload(
        section_number=str(raw_section.get("section_number")),
        prefix=raw_section.get("prefix"),
        title=raw_section.get("title") or "",
        text=raw_section.get("text") or "",
        depth=int(raw_section.get("depth", 1)),
        metadata=metadata,
        numbered_items=numbered_items,
        references=references,
        page_number=page_number,
    )


def _build_references(raw_references: Mapping[str, Any]) -> List[ReferencePayload]:
    """Normalize loose reference data coming from the parser."""

    references: List[ReferencePayload] = []

    for entry in raw_references.get("internal_sections", []):
        references.append(
            ReferencePayload(
                reference_type=str(entry.get("type") or "section"),
                reference_text=str(entry.get("reference") or ""),
                position_start=_safe_int(entry.get("position", {}).get("start")),
                position_end=_safe_int(entry.get("position", {}).get("end")),
            )
        )

    for entry in raw_references.get("external_documents", []):
        references.append(
            ReferencePayload(
                reference_type="external",
                reference_text=str(entry.get("reference") or ""),
                position_start=_safe_int(entry.get("position", {}).get("start")),
                position_end=_safe_int(entry.get("position", {}).get("end")),
            )
        )

    for table_id in raw_references.get("table", []) or []:
        references.append(
            ReferencePayload(
                reference_type="table",
                reference_text=str(table_id),
            )
        )

    for figure_id in raw_references.get("figures", []) or []:
        references.append(
            ReferencePayload(
                reference_type="figure",
                reference_text=str(figure_id),
            )
        )

    return references


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
