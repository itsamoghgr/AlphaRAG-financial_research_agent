"""Query log repository: writes one row per user query for eval and debugging."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from alpharag.db.models import QueryLog


class QueryLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        ticker: str,
        question: str,
        answer: str | None = None,
        retrieved_chunk_ids: list[str] | None = None,
        latency_ms_total: int | None = None,
        latency_ms_ingest: int | None = None,
        latency_ms_retrieve: int | None = None,
        latency_ms_generate: int | None = None,
        error: str | None = None,
    ) -> QueryLog:
        row = QueryLog(
            ticker=ticker.upper(),
            question=question,
            answer=answer,
            retrieved_chunk_ids=retrieved_chunk_ids,
            latency_ms_total=latency_ms_total,
            latency_ms_ingest=latency_ms_ingest,
            latency_ms_retrieve=latency_ms_retrieve,
            latency_ms_generate=latency_ms_generate,
            error=error,
        )
        self._session.add(row)
        await self._session.flush()
        return row
