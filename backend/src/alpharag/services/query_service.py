"""QueryService: orchestrates the full query lifecycle.

Wires together: TickerResolver -> ensure_ingested -> retrieve -> synthesize.

Emits typed events through an async generator so the API layer can forward
them directly as SSE without any extra plumbing. The service itself
imports nothing from FastAPI -- it is pure orchestration.

Event vocabulary (matches `api/sse.py`):
- StageEvent(stage=..., message=..., data={...})    progress markers
- TokenEvent(text=...)                              streamed answer fragments
- FinalEvent(answer, citations, timings_ms)         terminal success
- ErrorEvent(code, message)                         terminal failure
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from alpharag.api.sse import ErrorEvent, FinalEvent, StageEvent, TokenEvent
from alpharag.core.errors import AlphaRAGError
from alpharag.core.logging import get_logger
from alpharag.db.repositories.company_repo import CompanyRepository
from alpharag.db.repositories.query_log_repo import QueryLogRepository
from alpharag.generation.citation_parser import make_snippet, parse_citations
from alpharag.generation.prompts import assign_markers
from alpharag.generation.synthesizer import Synthesizer
from alpharag.retrieval.hybrid import HybridRetriever
from alpharag.services.ingestion_service import IngestionService

logger = get_logger(__name__)

QueryEvent = StageEvent | TokenEvent | FinalEvent | ErrorEvent


@dataclass(frozen=True, slots=True)
class QueryRequest:
    ticker: str
    question: str
    refresh: bool = False


class QueryService:
    def __init__(
        self,
        *,
        ingestion: IngestionService,
        retriever: HybridRetriever,
        synthesizer: Synthesizer,
    ) -> None:
        self._ingestion = ingestion
        self._retriever = retriever
        self._synth = synthesizer

    async def stream(
        self,
        session: AsyncSession,
        req: QueryRequest,
    ) -> AsyncIterator[QueryEvent]:
        """Run the full query and yield events. The session must be kept open
        for the duration of the generator.
        """
        t_start = time.monotonic()
        t_ingest_end = t_start
        t_retrieve_end = t_start

        try:
            # Buffer stage events from the ingestion service so we can both
            # forward them AND keep the rest of the orchestration sequential.
            staged_events: list[StageEvent] = []

            async def progress_cb(stage: str, msg: str, data: dict) -> None:
                staged_events.append(StageEvent(stage=stage, message=msg, data=data))  # type: ignore[arg-type]

            ingestion_result = await self._ingestion.ensure_ingested(
                session,
                ticker=req.ticker,
                force_refresh=req.refresh,
                progress=progress_cb,
            )
            for ev in staged_events:
                yield ev
            t_ingest_end = time.monotonic()

            # ---- Retrieve ----
            yield StageEvent(
                stage="retrieving",
                message="Searching the filings",
                data={"ticker": ingestion_result.ticker},
            )
            retrieval = await self._retriever.retrieve(
                session,
                company_id=UUID(ingestion_result.company_id),
                query=req.question,
                top_k=8,
            )
            t_retrieve_end = time.monotonic()

            if not retrieval.hits:
                # Be honest: tell the user instead of silently inventing an answer.
                yield FinalEvent(
                    answer=(
                        "The retrieved filings did not contain passages relevant "
                        "to this question."
                    ),
                    citations=[],
                    timings_ms=_timings(t_start, t_ingest_end, t_retrieve_end, t_retrieve_end),
                )
                return

            # ---- Generate (streamed) ----
            yield StageEvent(
                stage="generating",
                message="Writing the answer",
                data={"chunks_used": len(retrieval.hits)},
            )
            company_repo = CompanyRepository(session)
            company = await company_repo.get_by_id(UUID(ingestion_result.company_id))
            company_name = company.name if company else ingestion_result.ticker

            full_answer_parts: list[str] = []
            async for delta in self._synth.stream_synthesize(
                ticker=ingestion_result.ticker,
                company_name=company_name,
                question=req.question,
                hits=retrieval.hits,
            ):
                full_answer_parts.append(delta)
                yield TokenEvent(text=delta)

            answer = "".join(full_answer_parts)
            t_generate_end = time.monotonic()

            # ---- Validate citations + build final payload ----
            contexts = assign_markers(retrieval.hits)
            cite_result = parse_citations(answer=answer, contexts=contexts)

            citations = [
                {
                    "marker": rc.marker,
                    "chunk_id": str(rc.context.hit.chunk_id),
                    "section_id": str(rc.context.hit.section_id),
                    "ticker": ingestion_result.ticker,
                    "filing_id": str(rc.context.hit.filing_id),
                    "filing": f"{rc.context.hit.form_type} ({rc.context.hit.filing_date})",
                    "section": rc.context.hit.section_title,
                    "snippet": make_snippet(rc.context.hit.text),
                    "source_url": rc.context.hit.source_url,
                    "char_start": rc.context.hit.char_start,
                    "char_end": rc.context.hit.char_end,
                }
                for rc in cite_result.resolved
            ]

            timings = _timings(t_start, t_ingest_end, t_retrieve_end, t_generate_end)

            # Best-effort query log; don't fail the request if logging fails.
            try:
                await QueryLogRepository(session).record(
                    ticker=req.ticker,
                    question=req.question,
                    answer=answer,
                    retrieved_chunk_ids=[str(h.chunk_id) for h in retrieval.hits],
                    latency_ms_total=timings["total"],
                    latency_ms_ingest=timings["ingest"],
                    latency_ms_retrieve=timings["retrieve"],
                    latency_ms_generate=timings["generate"],
                )
            except Exception as e:  # pragma: no cover - logging side-effect only
                logger.warning("query_log_failed", error=str(e))

            yield FinalEvent(answer=answer, citations=citations, timings_ms=timings)

        except AlphaRAGError as e:
            logger.warning("query_failed", code=e.code, message=e.message)
            yield ErrorEvent(code=e.code, message=e.message)
        except Exception as e:
            logger.exception("query_unexpected_error")
            yield ErrorEvent(code="internal_error", message=str(e))


def _timings(
    t_start: float,
    t_ingest_end: float,
    t_retrieve_end: float,
    t_generate_end: float,
) -> dict[str, int]:
    def ms(start: float, end: float) -> int:
        return int((end - start) * 1000)

    return {
        "ingest": ms(t_start, t_ingest_end),
        "retrieve": ms(t_ingest_end, t_retrieve_end),
        "generate": ms(t_retrieve_end, t_generate_end),
        "total": ms(t_start, t_generate_end),
    }
