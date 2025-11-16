"""Reference type definitions for PDF document parsing."""

from typing import Optional
from pydantic import BaseModel, Field


class Position(BaseModel):
    """Position of a reference in text."""
    start: int = Field(..., description="Start position in text")
    end: int = Field(..., description="End position in text")


class Reference(BaseModel):
    """Base reference model."""
    type: str = Field(..., description="Type of reference (section, table, figure, external)")
    reference: str = Field(..., description="Reference text (e.g., 'Section 414')")
    position: Position = Field(..., description="Position in text")


class InternalSectionReference(Reference):
    """Internal section reference."""
    type: str = Field(default="section", description="Reference type")


class TableData(BaseModel):
    """Table structure data."""
    headers: list[str] = Field(default_factory=list, description="Table column headers")
    rows: list[list[str]] = Field(default_factory=list, description="Table rows")
    page: int = Field(..., description="Page number where table is located")
    accuracy: Optional[float] = Field(None, description="Extraction accuracy score (0-100)")


class TableReference(Reference):
    """Table reference with optional table data."""
    type: str = Field(default="table", description="Reference type")
    table_data: Optional[TableData] = Field(None, description="Extracted table structure and content")


class FigureReference(Reference):
    """Figure reference with image metadata."""
    type: str = Field(default="figure", description="Reference type")
    image_path: Optional[str] = Field(None, description="Path to extracted image file")
    page: Optional[int] = Field(None, description="Page number where figure is located")
    dimensions: Optional[dict[str, int]] = Field(None, description="Image dimensions (width, height)")
    format: Optional[str] = Field(None, description="Image format (png, jpeg, etc.)")


class ExternalDocumentReference(Reference):
    """External document reference."""
    type: str = Field(default="external", description="Reference type")


class References(BaseModel):
    """Collection of text references in a section (not actual extracted data)."""
    internal_sections: list[InternalSectionReference] = Field(
        default_factory=list,
        description="Internal section references (e.g., 'see Section 307.1')"
    )
    table: list[str] = Field(
        default_factory=list,
        description="Table IDs/references mentioned in text (e.g., ['307.1(1)', '307.1(2)'])"
    )
    external_documents: list[ExternalDocumentReference] = Field(
        default_factory=list,
        description="External document references"
    )
    figures: list[str] = Field(
        default_factory=list,
        description="Figure IDs mentioned or extracted in section (e.g., ['figure_705.7'])"
    )
