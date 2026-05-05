"""Company aggregate repository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alpharag.db.models import Company


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_ticker(self, ticker: str) -> Company | None:
        stmt = select(Company).where(Company.ticker == ticker.upper())
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_cik(self, cik: str) -> Company | None:
        stmt = select(Company).where(Company.cik == cik)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, company_id: UUID) -> Company | None:
        return await self._session.get(Company, company_id)

    async def upsert(
        self,
        *,
        ticker: str,
        cik: str,
        name: str,
        sic_sector: str | None = None,
        fiscal_year_end: str | None = None,
    ) -> Company:
        existing = await self.get_by_cik(cik)
        if existing is not None:
            existing.ticker = ticker.upper()
            existing.name = name
            if sic_sector is not None:
                existing.sic_sector = sic_sector
            if fiscal_year_end is not None:
                existing.fiscal_year_end = fiscal_year_end
            await self._session.flush()
            return existing

        company = Company(
            ticker=ticker.upper(),
            cik=cik,
            name=name,
            sic_sector=sic_sector,
            fiscal_year_end=fiscal_year_end,
        )
        self._session.add(company)
        await self._session.flush()
        return company

    async def mark_ingested(self, company_id: UUID, *, status: str) -> None:
        company = await self.get_by_id(company_id)
        if company is None:
            return
        company.last_ingested_at = datetime.now(UTC)
        company.last_ingest_status = status
        await self._session.flush()
