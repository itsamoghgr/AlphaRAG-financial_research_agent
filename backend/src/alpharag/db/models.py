"""SQLAlchemy 2.0 ORM models.

Schema mirrors the data model in the architecture plan. Notably:
- `chunks.company_id` is denormalized so retrieval can filter on a single
  indexed column with no joins on the hot path.
- `ingestion_jobs` is the source of truth for "what stage is the per-ticker
  ingestion in" and powers the SSE progress events.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    pass


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    cik: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sic_sector: Mapped[str | None] = mapped_column(String(64))
    fiscal_year_end: Mapped[str | None] = mapped_column(String(8))
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ingest_status: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    filings: Mapped[list[Filing]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class Filing(Base):
    __tablename__ = "filings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    form_type: Mapped[str] = mapped_column(String(16), nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_of_report: Mapped[date | None] = mapped_column(Date)
    accession_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_html_path: Mapped[str | None] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped[Company] = relationship(back_populates="filings")
    sections: Mapped[list[Section]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_filings_company_form_date", "company_id", "form_type", "filing_date"),
    )


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    filing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("filings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_code: Mapped[str | None] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    filing: Mapped[Filing] = relationship(back_populates="sections")
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)

    section: Mapped[Section] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_company_section", "company_id", "section_id"),
        # ivfflat / FTS indexes are created in Alembic with raw SQL since
        # they need post-data parameters (lists, opclasses) not expressible here.
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # running|succeeded|failed
    stage: Mapped[str | None] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSONB)


class QueryLog(Base):
    __tablename__ = "query_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    retrieved_chunk_ids: Mapped[list[str] | None] = mapped_column(JSONB)
    latency_ms_total: Mapped[int | None] = mapped_column(BigInteger)
    latency_ms_ingest: Mapped[int | None] = mapped_column(BigInteger)
    latency_ms_retrieve: Mapped[int | None] = mapped_column(BigInteger)
    latency_ms_generate: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = [
    "Base",
    "Chunk",
    "Company",
    "Filing",
    "IngestionJob",
    "QueryLog",
    "Section",
]
