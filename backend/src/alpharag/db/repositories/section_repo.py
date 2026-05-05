"""Section aggregate repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alpharag.db.models import Section


class SectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, section_id: UUID) -> Section | None:
        return await self._session.get(Section, section_id)

    async def list_for_filing(self, filing_id: UUID) -> list[Section]:
        stmt = select(Section).where(Section.filing_id == filing_id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def create(
        self,
        *,
        filing_id: UUID,
        item_code: str | None,
        title: str,
        char_start: int,
        char_end: int,
        text: str,
    ) -> Section:
        section = Section(
            filing_id=filing_id,
            item_code=item_code,
            title=title,
            char_start=char_start,
            char_end=char_end,
            text=text,
        )
        self._session.add(section)
        await self._session.flush()
        return section
