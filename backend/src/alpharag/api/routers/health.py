"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from alpharag import __version__
from alpharag.api.dependencies import SessionDep
from alpharag.api.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(session: SessionDep) -> HealthResponse:
    db_ok = False
    try:
        result = await session.execute(text("SELECT 1"))
        db_ok = result.scalar_one() == 1
    except Exception:
        db_ok = False
    return HealthResponse(status="ok", version=__version__, db_connected=db_ok)
