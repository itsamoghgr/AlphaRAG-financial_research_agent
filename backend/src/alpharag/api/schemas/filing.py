"""Filing and section response shapes."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class FilingSummary(BaseModel):
    id: str
    form_type: str
    filing_date: date
    period_of_report: date | None
    accession_no: str
    source_url: str


class CompanyStatus(BaseModel):
    ticker: str
    cik: str | None
    name: str | None
    is_cached: bool
    last_ingested_at: str | None
    filings: list[FilingSummary]


class SectionContent(BaseModel):
    id: str
    item_code: str | None
    title: str
    text: str
    char_start: int
    char_end: int
