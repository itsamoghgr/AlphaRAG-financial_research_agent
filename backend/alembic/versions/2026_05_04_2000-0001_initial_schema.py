"""Initial schema: companies, filings, sections, chunks, ingestion_jobs, query_log.

Revision ID: 0001
Revises:
Create Date: 2026-05-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(16), nullable=False, unique=True),
        sa.Column("cik", sa.String(10), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sic_sector", sa.String(64)),
        sa.Column("fiscal_year_end", sa.String(8)),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True)),
        sa.Column("last_ingest_status", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_companies_ticker", "companies", ["ticker"])
    op.create_index("ix_companies_cik", "companies", ["cik"])

    op.create_table(
        "filings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("form_type", sa.String(16), nullable=False),
        sa.Column("filing_date", sa.Date, nullable=False),
        sa.Column("period_of_report", sa.Date),
        sa.Column("accession_no", sa.String(32), nullable=False, unique=True),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("raw_html_path", sa.Text),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_filings_company_id", "filings", ["company_id"])
    op.create_index("ix_filings_company_form_date", "filings", ["company_id", "form_type", "filing_date"])

    op.create_table(
        "sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("filings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_code", sa.String(16)),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("char_start", sa.Integer, nullable=False),
        sa.Column("char_end", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
    )
    op.create_index("ix_sections_filing_id", "sections", ["filing_id"])

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("char_start", sa.Integer, nullable=False),
        sa.Column("char_end", sa.Integer, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
    )
    op.create_index("ix_chunks_section_id", "chunks", ["section_id"])
    op.create_index("ix_chunks_company_id", "chunks", ["company_id"])
    op.create_index("ix_chunks_company_section", "chunks", ["company_id", "section_id"])

    # Vector index (cosine). lists=100 is fine for the small MVP corpus
    # (well under 1M vectors); tune up later if needed.
    op.execute(
        "CREATE INDEX ix_chunks_embedding_cosine ON chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    op.execute(
        "CREATE INDEX ix_chunks_text_fts ON chunks "
        "USING GIN (to_tsvector('english', text))"
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stage", sa.String(32)),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text),
        sa.Column("details", postgresql.JSONB),
    )
    op.create_index("ix_ingestion_jobs_company_id", "ingestion_jobs", ["company_id"])

    op.create_table(
        "query_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text),
        sa.Column("retrieved_chunk_ids", postgresql.JSONB),
        sa.Column("latency_ms_total", sa.BigInteger),
        sa.Column("latency_ms_ingest", sa.BigInteger),
        sa.Column("latency_ms_retrieve", sa.BigInteger),
        sa.Column("latency_ms_generate", sa.BigInteger),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_query_log_ticker", "query_log", ["ticker"])


def downgrade() -> None:
    op.drop_index("ix_query_log_ticker", table_name="query_log")
    op.drop_table("query_log")
    op.drop_index("ix_ingestion_jobs_company_id", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.execute("DROP INDEX IF EXISTS ix_chunks_text_fts")
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_cosine")
    op.drop_index("ix_chunks_company_section", table_name="chunks")
    op.drop_index("ix_chunks_company_id", table_name="chunks")
    op.drop_index("ix_chunks_section_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_sections_filing_id", table_name="sections")
    op.drop_table("sections")
    op.drop_index("ix_filings_company_form_date", table_name="filings")
    op.drop_index("ix_filings_company_id", table_name="filings")
    op.drop_table("filings")
    op.drop_index("ix_companies_cik", table_name="companies")
    op.drop_index("ix_companies_ticker", table_name="companies")
    op.drop_table("companies")
