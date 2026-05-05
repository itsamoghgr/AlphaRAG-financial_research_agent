"""End-to-end eval runner for AlphaRAG.

Runs every Q/A pair in `eval_set.yaml` through the full QueryService stack
and reports:
- retrieval recall@k: did at least one returned chunk's section title
  contain one of the expected keywords?
- answer-correctness rate (heuristic): does the final answer contain at
  least one of the expected substrings?
- has-citations rate: did the LLM produce >=1 valid citation?
- per-question latency (ingest, retrieve, generate, total).

Costs money to run (OpenAI calls + EDGAR ingestion of any uncached tickers),
which is why it's gated behind the `eval` pytest marker. Run directly with:

    python -m tests.eval.run_eval

or pick a single ticker:

    python -m tests.eval.run_eval --ticker AAPL

Requires the database to be running and migrated.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

from alpharag.api.sse import FinalEvent, StageEvent
from alpharag.core.logging import configure_logging, get_logger
from alpharag.db.session import dispose_engine, session_scope
from alpharag.generation.synthesizer import Synthesizer
from alpharag.ingestion.edgar_client import EdgarClient
from alpharag.ingestion.parser import FilingParser
from alpharag.ingestion.ticker_resolver import TickerResolver
from alpharag.llm import OpenAIChatClient, OpenAIEmbeddingsClient
from alpharag.retrieval.hybrid import HybridRetriever
from alpharag.services.ingestion_service import IngestionService
from alpharag.services.query_service import QueryRequest, QueryService

EVAL_FILE = Path(__file__).parent / "eval_set.yaml"


@dataclass
class CaseResult:
    ticker: str
    question: str
    retrieval_hit: bool
    answer_match: bool
    has_citations: bool
    latency_ms: dict
    answer: str
    citations: list


def _load_cases(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def _check_retrieval_hit(stage_events: list[StageEvent], expected_keywords: list[str], citations: list) -> bool:
    """We don't have direct access to the retriever's hits in the SSE stream
    (only the citations the LLM ended up using), so we approximate
    retrieval recall as "at least one citation's section matched a keyword".
    This is a tighter metric (it requires the LLM to also find the chunk
    relevant) but it's the best signal we get from the public stream.
    """
    if not citations:
        return False
    needles = [k.lower() for k in expected_keywords]
    for c in citations:
        section = (c.get("section") or "").lower()
        if any(n in section for n in needles):
            return True
    return False


def _check_answer_match(answer: str, expected_phrases: list[str]) -> bool:
    a = answer.lower()
    return any(phrase.lower() in a for phrase in expected_phrases)


async def _run_case(service: QueryService, case: dict) -> CaseResult:
    final: FinalEvent | None = None
    citations: list = []
    answer = ""
    latency: dict = {}

    async with session_scope() as session:
        async for event in service.stream(
            session,
            QueryRequest(
                ticker=case["ticker"],
                question=case["question"],
                refresh=False,
            ),
        ):
            if isinstance(event, FinalEvent):
                final = event
                citations = event.citations
                answer = event.answer
                latency = event.timings_ms

    expected_kw = case.get("expected_section_keywords") or []
    expected_phrases = case.get("expected_answer_contains") or []

    return CaseResult(
        ticker=case["ticker"],
        question=case["question"],
        retrieval_hit=_check_retrieval_hit([], expected_kw, citations),
        answer_match=_check_answer_match(answer, expected_phrases) if final else False,
        has_citations=bool(citations),
        latency_ms=latency,
        answer=answer,
        citations=citations,
    )


async def _main(filter_ticker: str | None) -> int:
    configure_logging("WARNING")
    log = get_logger("eval")

    service = QueryService(
        ingestion=IngestionService(
            ticker_resolver=TickerResolver(),
            edgar_client=EdgarClient(),
            embeddings_client=OpenAIEmbeddingsClient(),
            parser=FilingParser(),
        ),
        retriever=HybridRetriever(OpenAIEmbeddingsClient()),
        synthesizer=Synthesizer(OpenAIChatClient()),
    )

    cases = _load_cases(EVAL_FILE)
    if filter_ticker:
        cases = [c for c in cases if c["ticker"].upper() == filter_ticker.upper()]
    if not cases:
        sys.stderr.write("No cases to run.\n")
        return 1

    results: list[CaseResult] = []
    for i, case in enumerate(cases, 1):
        log.info("eval_case_start", n=i, total=len(cases), ticker=case["ticker"])
        try:
            r = await _run_case(service, case)
        except Exception as e:
            log.error("eval_case_error", ticker=case["ticker"], error=str(e))
            results.append(
                CaseResult(
                    ticker=case["ticker"],
                    question=case["question"],
                    retrieval_hit=False,
                    answer_match=False,
                    has_citations=False,
                    latency_ms={},
                    answer="",
                    citations=[],
                )
            )
            continue
        status = (
            "PASS"
            if r.retrieval_hit and r.answer_match and r.has_citations
            else "PART"
            if r.retrieval_hit or r.answer_match
            else "FAIL"
        )
        print(
            f"[{status}] {r.ticker:5s} {r.latency_ms.get('total', 0):>5d}ms  "
            f"recall={int(r.retrieval_hit)} answer={int(r.answer_match)} "
            f"cited={int(r.has_citations)}  {case['question'][:80]}"
        )
        results.append(r)

    await dispose_engine()
    _report(results)
    fully_passing = sum(
        1 for r in results if r.retrieval_hit and r.answer_match and r.has_citations
    )
    return 0 if fully_passing >= len(results) * 0.6 else 1


def _report(results: list[CaseResult]) -> None:
    n = len(results)
    if n == 0:
        return
    recall = sum(1 for r in results if r.retrieval_hit) / n
    answer = sum(1 for r in results if r.answer_match) / n
    cited = sum(1 for r in results if r.has_citations) / n
    by_ticker = Counter(r.ticker for r in results)
    pass_by_ticker: Counter[str] = Counter()
    for r in results:
        if r.retrieval_hit and r.answer_match and r.has_citations:
            pass_by_ticker[r.ticker] += 1
    print()
    print("=" * 60)
    print("Eval summary")
    print("=" * 60)
    print(f"Cases:                {n}")
    print(f"Retrieval recall@k:   {recall:.0%}")
    print(f"Answer correctness:   {answer:.0%}")
    print(f"Has citations:        {cited:.0%}")
    print()
    print("Pass rate per ticker:")
    for ticker, total in sorted(by_ticker.items()):
        passed = pass_by_ticker.get(ticker, 0)
        print(f"  {ticker:5s} {passed}/{total}  ({passed / total:.0%})")
    avg = {
        k: int(sum(r.latency_ms.get(k, 0) for r in results) / max(n, 1))
        for k in ("ingest", "retrieve", "generate", "total")
    }
    print()
    print("Avg latency (ms):")
    for k, v in avg.items():
        print(f"  {k:9s} {v:>6d}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AlphaRAG eval suite.")
    parser.add_argument("--ticker", help="Filter to a single ticker.")
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args.ticker)))


if __name__ == "__main__":
    main()
