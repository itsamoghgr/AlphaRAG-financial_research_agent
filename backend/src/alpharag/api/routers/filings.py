"""GET /api/filings/{filing_id}/sections/{section_id}.

Used by the frontend's FilingViewer to fetch the source text behind a
citation deep-link. Returns just the section's text + char range -- the UI
already knows the chunk's offsets within the section.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from alpharag.api.dependencies import SessionDep
from alpharag.api.schemas.filing import SectionContent
from alpharag.db.repositories.section_repo import SectionRepository

router = APIRouter(prefix="/api/filings", tags=["filings"])


@router.get(
    "/{filing_id}/sections/{section_id}",
    response_model=SectionContent,
)
async def get_section(
    filing_id: str,
    section_id: str,
    session: SessionDep,
) -> SectionContent:
    try:
        section_uuid = UUID(section_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid section_id") from None
    try:
        UUID(filing_id)  # validate format only; real check is below
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filing_id") from None

    section = await SectionRepository(session).get_by_id(section_uuid)
    if section is None or str(section.filing_id) != filing_id:
        raise HTTPException(status_code=404, detail="Section not found")

    return SectionContent(
        id=str(section.id),
        item_code=section.item_code,
        title=section.title,
        text=section.text,
        char_start=section.char_start,
        char_end=section.char_end,
    )
