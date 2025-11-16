"""API request/response models with validation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Query Endpoint Models
# ============================================================================

class QueryOptionsModel(BaseModel):
    """Options for customizing query behavior."""
    
    max_sections: Optional[int] = Field(
        default=None,
        ge=1,
        le=50,
        description="Maximum number of sections to retrieve"
    )
    include_tables: bool = Field(
        default=True,
        description="Include table references in results"
    )
    include_figures: bool = Field(
        default=True,
        description="Include figure references in results"
    )
    search_type: str = Field(
        default="hybrid",
        pattern="^(hybrid|vector)$",
        description="Search strategy: 'hybrid' or 'vector'"
    )

    @field_validator("search_type")
    @classmethod
    def validate_search_type(cls, v: str) -> str:
        """Validate search type is valid."""
        if v not in ("hybrid", "vector"):
            raise ValueError("search_type must be 'hybrid' or 'vector'")
        return v


class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User query string"
    )
    options: Optional[QueryOptionsModel] = Field(
        default=None,
        description="Optional query configuration"
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Ensure query is not empty after stripping."""
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()


class CitationModel(BaseModel):
    """Citation information for a source."""
    
    section_number: str
    title: str
    chapter: Optional[int] = None
    page: Optional[str] = None


class SectionSummaryModel(BaseModel):
    """Summary of a section result."""
    
    id: int
    section_number: str
    title: str
    text: str
    chapter_number: Optional[int] = None
    chapter_title: Optional[str] = None
    parent_section_id: Optional[int] = None
    page_number: Optional[str] = None
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueryResultModel(BaseModel):
    """Complete query result with answer and context."""
    
    query: str
    answer: str
    citations: List[CitationModel] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    sections: List[SectionSummaryModel] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Search Endpoint Models
# ============================================================================

class SearchResultModel(BaseModel):
    """Search result for a single section."""
    
    section_number: str
    title: str
    text: str = Field(..., max_length=10000)
    chapter_number: Optional[int] = None
    chapter_title: Optional[str] = None
    page_number: Optional[str] = None
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class SearchResponse(BaseModel):
    """Search response with results."""
    
    query: str
    results: List[SearchResultModel] = Field(default_factory=list)
    count: int = Field(..., ge=0)

    @field_validator("count")
    @classmethod
    def validate_count_matches_results(cls, v: int, info) -> int:
        """Ensure count matches actual results length."""
        results = info.data.get("results", [])
        if v != len(results):
            raise ValueError("Count must match number of results")
        return v


# ============================================================================
# Section Detail Models
# ============================================================================

class SectionDetailModel(BaseModel):
    """Detailed section information with relationships."""
    
    section: SectionSummaryModel
    parent: Optional[SectionSummaryModel] = None
    children: List[SectionSummaryModel] = Field(default_factory=list)
    references: Dict[str, Any] = Field(default_factory=dict)
