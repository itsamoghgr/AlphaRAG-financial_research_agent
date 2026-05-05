"""Query request and response shapes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    question: str = Field(min_length=3, max_length=2000)
    refresh: bool = False


class Citation(BaseModel):
    marker: str  # "c1", "c2", ...
    chunk_id: str
    section_id: str
    ticker: str
    filing_id: str
    filing: str  # human label e.g. "10-K FY2024"
    section: str
    snippet: str
    source_url: str
    char_start: int
    char_end: int


class QueryAnswer(BaseModel):
    answer: str
    citations: list[Citation]
    timings_ms: dict[str, int]
