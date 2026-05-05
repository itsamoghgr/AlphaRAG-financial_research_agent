"""On-demand ingestion service.

This is the single source of truth for ingestion. It is called from:
- the query path (M4: QueryService) when a ticker is missing or stale
- the warmup CLI (`scripts/warmup.py`) for batch pre-loading

Idempotency:
- Filings are looked up by `accession_no`; existing ones are skipped.
- The whole flow is wrapped in a per-CIK Postgres advisory lock so two
  concurrent first-queries never duplicate work.

Progress reporting:
- The caller passes a `progress_cb` async callable that gets invoked at
  each stage. The QueryService bridges this into SSE events; the warmup
  CLI just logs.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from alpharag.core.errors import IngestionError, NoFilingsFoundError
from alpharag.core.logging import get_logger
from alpharag.db.models import Company
from alpharag.db.repositories.chunk_repo import ChunkInsert, ChunkRepository
from alpharag.db.repositories.company_repo import CompanyRepository
from alpharag.db.repositories.filing_repo import FilingRepository
from alpharag.db.repositories.ingestion_job_repo import IngestionJobRepository
from alpharag.db.repositories.section_repo import SectionRepository
from alpharag.ingestion.chunker import chunk_section
from alpharag.ingestion.edgar_client import EdgarClient, FilingMetadata
from alpharag.ingestion.embedder import embed_in_batches
from alpharag.ingestion.parser import FilingParser
from alpharag.ingestion.ticker_resolver import TickerInfo, TickerResolver
from alpharag.llm.base import EmbeddingsClient
from alpharag.services.freshness_policy import evaluate_freshness
from alpharag.services.locks import acquire_ingestion_lock

logger = get_logger(__name__)

Stage = Literal[
    "resolving",
    "cache_hit",
    "fetching",
    "parsing",
    "chunking",
    "embedding",
    "persisting",
]

ProgressCB = Callable[[Stage, str, dict], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class IngestionResult:
    company_id: str
    ticker: str
    cik: str
    cache_hit: bool
    filings_ingested: int
    chunks_created: int


async def _noop_progress(_stage: Stage, _msg: str, _data: dict) -> None:
    pass


class IngestionService:
    def __init__(
        self,
        *,
        ticker_resolver: TickerResolver,
        edgar_client: EdgarClient,
        embeddings_client: EmbeddingsClient,
        parser: FilingParser | None = None,
    ) -> None:
        self._tickers = ticker_resolver
        self._edgar = edgar_client
        self._embeddings = embeddings_client
        self._parser = parser or FilingParser()

    async def ensure_ingested(
        self,
        session: AsyncSession,
        *,
        ticker: str,
        force_refresh: bool = False,
        progress: ProgressCB = _noop_progress,
    ) -> IngestionResult:
        """Make sure this ticker has fresh filings in the DB. Idempotent.

        Returns IngestionResult.cache_hit=True if no work was done.
        """
        from alpharag.core.config import get_settings

        settings = get_settings()

        await progress("resolving", "Looking up company", {"ticker": ticker})
        info = await self._tickers.resolve(ticker)

        # Acquire the per-CIK lock BEFORE the freshness check, so two
        # concurrent callers serialize and the second one sees the cache hit.
        await acquire_ingestion_lock(session, cik=info.cik)

        company_repo = CompanyRepository(session)
        company = await company_repo.get_by_cik(info.cik)
        decision = evaluate_freshness(company, force_refresh=force_refresh)

        if decision.is_fresh and company is not None:
            await progress(
                "cache_hit",
                "Filings already loaded and fresh",
                {"reason": decision.reason},
            )
            return IngestionResult(
                company_id=str(company.id),
                ticker=info.ticker,
                cik=info.cik,
                cache_hit=True,
                filings_ingested=0,
                chunks_created=0,
            )

        # Fetch metadata once and upsert the company row so we have an ID
        # for the ingestion job.
        meta = await self._edgar.get_company_metadata(cik=info.cik)
        company = await company_repo.upsert(
            ticker=info.ticker,
            cik=info.cik,
            name=meta.get("name") or info.name,
            sic_sector=meta.get("sicDescription"),
            fiscal_year_end=meta.get("fiscalYearEnd"),
        )

        job_repo = IngestionJobRepository(session)
        job = await job_repo.start(company_id=company.id)

        try:
            return await self._run_ingestion(
                session,
                company=company,
                info=info,
                progress=progress,
                num_10k=settings.ingest_num_10k,
                num_10q=settings.ingest_num_10q,
            )
        except Exception as e:
            await job_repo.fail(job.id, error=str(e))
            await company_repo.mark_ingested(company.id, status="failed")
            logger.exception("ingestion_failed", ticker=ticker, cik=info.cik)
            raise IngestionError(f"Ingestion failed for {ticker}: {e}") from e
        finally:
            # The advisory lock is released automatically at COMMIT/ROLLBACK,
            # which the surrounding session_scope handles.
            pass

    async def _run_ingestion(
        self,
        session: AsyncSession,
        *,
        company: Company,
        info: TickerInfo,
        progress: ProgressCB,
        num_10k: int,
        num_10q: int,
    ) -> IngestionResult:
        company_repo = CompanyRepository(session)
        filing_repo = FilingRepository(session)
        section_repo = SectionRepository(session)
        chunk_repo = ChunkRepository(session)

        await progress("fetching", "Looking up filings on SEC EDGAR", {})
        filings = await self._edgar.list_filings(
            cik=info.cik,
            form_types=["10-K", "10-Q"],
            max_per_form={"10-K": num_10k, "10-Q": num_10q},
        )
        if not filings:
            raise NoFilingsFoundError(
                f"No 10-K or 10-Q filings found for {info.ticker}",
                details={"ticker": info.ticker, "cik": info.cik},
            )

        new_filings: list[FilingMetadata] = []
        for f in filings:
            existing = await filing_repo.get_by_accession(f.accession_no)
            if existing is None:
                new_filings.append(f)

        if not new_filings:
            await progress(
                "cache_hit",
                "All filings already ingested",
                {"checked": len(filings)},
            )
            await company_repo.mark_ingested(company.id, status="succeeded")
            return IngestionResult(
                company_id=str(company.id),
                ticker=info.ticker,
                cik=info.cik,
                cache_hit=True,
                filings_ingested=0,
                chunks_created=0,
            )

        total_chunks = 0
        for idx, f_meta in enumerate(new_filings):
            await progress(
                "fetching",
                f"Downloading {f_meta.form_type} {f_meta.filing_date}",
                {"current": idx + 1, "total": len(new_filings)},
            )
            html, cache_path = await self._edgar.fetch_filing_html(
                cik=info.cik, filing=f_meta
            )

            await progress(
                "parsing",
                f"Parsing {f_meta.form_type} {f_meta.filing_date}",
                {"current": idx + 1, "total": len(new_filings)},
            )
            parsed = self._parser.parse(html)
            if not parsed.sections:
                logger.warning("parser_returned_no_sections", accession=f_meta.accession_no)
                continue

            filing_row = await filing_repo.create(
                company_id=company.id,
                form_type=f_meta.form_type,
                filing_date=f_meta.filing_date,
                period_of_report=f_meta.period_of_report,
                accession_no=f_meta.accession_no,
                source_url=f_meta.source_url,
                raw_html_path=str(cache_path),
            )

            await progress(
                "chunking",
                f"Splitting into chunks ({len(parsed.sections)} sections)",
                {"current": idx + 1, "total": len(new_filings)},
            )
            all_chunks_for_filing = []
            for parsed_section in parsed.sections:
                section_row = await section_repo.create(
                    filing_id=filing_row.id,
                    item_code=parsed_section.item_code,
                    title=parsed_section.title,
                    char_start=parsed_section.char_start,
                    char_end=parsed_section.char_end,
                    text=parsed_section.text,
                )
                section_chunks = chunk_section(
                    parsed_section,
                    company_name=company.name,
                    form_type=f_meta.form_type,
                    filing_date=str(f_meta.filing_date),
                )
                for c in section_chunks:
                    all_chunks_for_filing.append((section_row.id, c))

            if not all_chunks_for_filing:
                continue

            await progress(
                "embedding",
                f"Creating embeddings ({len(all_chunks_for_filing)} chunks)",
                {"current": idx + 1, "total": len(new_filings)},
            )
            embed_texts = [c.embed_text for (_sid, c) in all_chunks_for_filing]
            embeddings = await embed_in_batches(self._embeddings, embed_texts)
            if len(embeddings) != len(all_chunks_for_filing):
                raise IngestionError(
                    "Embedding count mismatch: "
                    f"{len(embeddings)} != {len(all_chunks_for_filing)}"
                )

            await progress(
                "persisting",
                f"Saving chunks for {f_meta.form_type} {f_meta.filing_date}",
                {"current": idx + 1, "total": len(new_filings)},
            )
            inserts = [
                ChunkInsert(
                    section_id=sid,
                    company_id=company.id,
                    chunk_index=c.chunk_index,
                    text=c.text,
                    char_start=c.char_start,
                    char_end=c.char_end,
                    token_count=c.token_count,
                    embedding=embeddings[i],
                )
                for i, (sid, c) in enumerate(all_chunks_for_filing)
            ]
            await chunk_repo.bulk_insert(inserts)
            total_chunks += len(inserts)

        await company_repo.mark_ingested(company.id, status="succeeded")
        # Update the in-memory copy so subsequent reads in this session see fresh state.
        company.last_ingested_at = datetime.now(UTC)

        return IngestionResult(
            company_id=str(company.id),
            ticker=info.ticker,
            cik=info.cik,
            cache_hit=False,
            filings_ingested=len(new_filings),
            chunks_created=total_chunks,
        )
