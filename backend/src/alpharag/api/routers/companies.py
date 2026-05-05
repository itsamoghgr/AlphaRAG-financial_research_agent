"""GET /api/companies/{ticker}/status.

Lightweight status endpoint the frontend uses to show whether a ticker is
already cached and what filings are available. Does not trigger ingestion.
"""

from __future__ import annotations

from fastapi import APIRouter

from alpharag.api.dependencies import SessionDep, TickerResolverDep
from alpharag.api.schemas.filing import CompanyStatus, FilingSummary
from alpharag.core.errors import UnknownTickerError
from alpharag.db.repositories.company_repo import CompanyRepository
from alpharag.db.repositories.filing_repo import FilingRepository

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/{ticker}/status", response_model=CompanyStatus)
async def company_status(
    ticker: str,
    session: SessionDep,
    resolver: TickerResolverDep,
) -> CompanyStatus:
    ticker_upper = ticker.strip().upper()

    try:
        info = await resolver.resolve(ticker_upper)
    except UnknownTickerError:
        return CompanyStatus(
            ticker=ticker_upper,
            cik=None,
            name=None,
            is_cached=False,
            last_ingested_at=None,
            filings=[],
        )

    repo = CompanyRepository(session)
    company = await repo.get_by_cik(info.cik)
    if company is None:
        return CompanyStatus(
            ticker=info.ticker,
            cik=info.cik,
            name=info.name,
            is_cached=False,
            last_ingested_at=None,
            filings=[],
        )

    filings = await FilingRepository(session).list_for_company(company.id)
    return CompanyStatus(
        ticker=info.ticker,
        cik=info.cik,
        name=company.name,
        is_cached=company.last_ingested_at is not None,
        last_ingested_at=(
            company.last_ingested_at.isoformat()
            if company.last_ingested_at
            else None
        ),
        filings=[
            FilingSummary(
                id=str(f.id),
                form_type=f.form_type,
                filing_date=f.filing_date,
                period_of_report=f.period_of_report,
                accession_no=f.accession_no,
                source_url=f.source_url,
            )
            for f in filings
        ],
    )
