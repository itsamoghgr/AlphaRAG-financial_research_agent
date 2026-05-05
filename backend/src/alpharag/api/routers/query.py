"""POST /api/query (SSE).

The handler is intentionally tiny: it builds the request DTO, opens a DB
session, and forwards events from `QueryService.stream()` to the SSE
response. All real work lives in the service.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from alpharag.api.dependencies import QueryServiceDep, SessionDep
from alpharag.api.schemas.query import QueryRequest as QueryRequestDTO
from alpharag.services.query_service import QueryRequest as ServiceQueryRequest

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query")
async def query(
    body: QueryRequestDTO,
    session: SessionDep,
    service: QueryServiceDep,
):
    async def event_stream() -> AsyncIterator[dict]:
        req = ServiceQueryRequest(
            ticker=body.ticker.strip().upper(),
            question=body.question.strip(),
            refresh=body.refresh,
        )
        async for event in service.stream(session, req):
            yield event.to_sse()

    return EventSourceResponse(event_stream())
