"""Document structure models for PDF parsing."""

from typing import Optional
from pydantic import BaseModel, Field

from .references import References


class NumberedItem(BaseModel):
    """Numbered list item within a section."""
    number: int = Field(..., description="Item number")
    text: str = Field(..., description="Item text content")


class Metadata(BaseModel):
    """Section metadata."""
    has_table: bool = Field(default=False, description="Whether section contains tables")
    has_figure: bool = Field(default=False, description="Whether section contains figures")
    table_count: int = Field(default=0, description="Number of tables in section")
    figure_count: int = Field(default=0, description="Number of figures in section")
    page_number: str = Field(..., description="Page number(s) where section appears (e.g., '3-4')")


class Section(BaseModel):
    """Section within a chapter."""
    section_number: str = Field(..., description="Section number (e.g., '307', '307.1')")
    prefix: Optional[str] = Field(None, description="Section prefix ([A], [F], [BS], etc.)")
    title: str = Field(..., description="Section title")
    text: str = Field(default="", description="Section text content")
    depth: int = Field(..., description="Section depth (0 for base sections, 1+ for subsections)")
    numbered_items: list[NumberedItem] = Field(
        default_factory=list,
        description="Numbered list items"
    )
    subsections: list['Section'] = Field(
        default_factory=list,
        description="Nested subsections"
    )
    references: References = Field(
        default_factory=References,
        description="References found in section"
    )
    metadata: Optional[Metadata] = Field(None, description="Section metadata")


# Enable forward references for recursive model
Section.model_rebuild()


class Part(BaseModel):
    """Part within a chapter (e.g., PART 1—SCOPE AND APPLICATION)."""
    part_number: int = Field(..., description="Part number")
    title: str = Field(..., description="Part title")
    sections: list[Section] = Field(
        default_factory=list,
        description="Sections within this part"
    )


class Chapter(BaseModel):
    """Chapter within the document."""
    chapter_number: int = Field(..., description="Chapter number")
    title: str = Field(..., description="Chapter title")
    user_notes: Optional[str] = Field(None, description="User notes/introduction text for the chapter")
    parts: list[Part] = Field(
        default_factory=list,
        description="Parts within the chapter"
    )
    sections: list[Section] = Field(
        default_factory=list,
        description="Top-level sections in chapter (sections not in a part)"
    )


class Document(BaseModel):
    """Root document model."""
    title: str = Field(..., description="Document title")
    version: str = Field(..., description="Document version")
    chapters: list[Chapter] = Field(
        default_factory=list,
        description="Document chapters"
    )
    
    def model_dump_json(self, **kwargs) -> str:
        """Export to JSON string with pretty formatting."""
        if 'indent' not in kwargs:
            kwargs['indent'] = 2
        return super().model_dump_json(**kwargs)
