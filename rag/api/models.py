"""API request/response models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryOptionsModel(BaseModel):
    max_sections: Optional[int] = Field(default=None, ge=1, le=50)
    include_tables: bool = True
    include_figures: bool = True
    search_type: str = Field(default="hybrid", pattern="^(hybrid|vector)$")


class QueryRequest(BaseModel):
    query: str
    options: Optional[QueryOptionsModel] = None


class CitationModel(BaseModel):
    section_number: str
    title: str
    chapter: Optional[int] = None
    page: Optional[str] = None


class SectionSummaryModel(BaseModel):
    id: int
    section_number: str
    title: str
    text: str
    chapter_number: Optional[int] = None
    chapter_title: Optional[str] = None
    parent_section_id: Optional[int] = None
    page_number: Optional[str] = None
    score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueryResultModel(BaseModel):
    query: str
    answer: str
    citations: List[CitationModel]
    metadata: Dict[str, Any]
    sections: List[SectionSummaryModel]
    context: Dict[str, Any]


class SearchResultModel(BaseModel):
    section_number: str
    title: str
    text: str
    chapter_number: Optional[int] = None
    chapter_title: Optional[str] = None
    page_number: Optional[str] = None
    score: Optional[float] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultModel]
    count: int


class SectionDetailModel(BaseModel):
    section: SectionSummaryModel
    parent: Optional[SectionSummaryModel] = None
    children: List[SectionSummaryModel] = Field(default_factory=list)
    references: Dict[str, Any] = Field(default_factory=dict)
