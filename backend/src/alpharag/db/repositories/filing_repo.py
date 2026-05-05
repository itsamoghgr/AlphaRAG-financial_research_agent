"""Filing aggregate repository."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alpharag.db.models import Filing


class FilingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, filing_id: UUID) -> Filing | None:
        return await self._session.get(Filing, filing_id)

    async def get_by_accession(self, accession_no: str) -> Filing | None:
        stmt = select(Filing).where(Filing.accession_no == accession_no)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_company(
        self,
        company_id: UUID,
        *,
        form_types: list[str] | None = None,
    ) -> list[Filing]:
        stmt = select(Filing).where(Filing.company_id == company_id)
        if form_types:
            stmt = stmt.where(Filing.form_type.in_(form_types))
        stmt = stmt.order_by(Filing.filing_date.desc())
        return list((await self._session.execute(stmt)).scalars().all())

    async def latest_filing_date(self, company_id: UUID) -> date | None:
        stmt = (
            select(Filing.filing_date)
            .where(Filing.company_id == company_id)
            .order_by(Filing.filing_date.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(
        self,
        *,
        company_id: UUID,
        form_type: str,
        filing_date: date,
        period_of_report: date | None,
        accession_no: str,
        source_url: str,
        raw_html_path: str | None,
    ) -> Filing:
        filing = Filing(
            company_id=company_id,
            form_type=form_type,
            filing_date=filing_date,
            period_of_report=period_of_report,
            accession_no=accession_no,
            source_url=source_url,
            raw_html_path=raw_html_path,
        )
        self._session.add(filing)
        await self._session.flush()
        return filing
