"""pytest-driven eval. Marked `eval`; gated out of the default suite.

Run with:
    pytest -m eval

Requires Postgres to be running, OPENAI_API_KEY to be set, and SEC_USER_AGENT
to contain a real email. First run will ingest filings (~10-25s per new
ticker); subsequent runs hit the cache.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml

from alpharag.generation.synthesizer import Synthesizer
from alpharag.ingestion.edgar_client import EdgarClient
from alpharag.ingestion.parser import FilingParser
from alpharag.ingestion.ticker_resolver import TickerResolver
from alpharag.llm import OpenAIChatClient, OpenAIEmbeddingsClient
from alpharag.retrieval.hybrid import HybridRetriever
from alpharag.services.ingestion_service import IngestionService
from alpharag.services.query_service import QueryService
from tests.eval.run_eval import _run_case

EVAL_FILE = Path(__file__).parent / "eval_set.yaml"


def _load_cases():
    with EVAL_FILE.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def _service() -> QueryService:
    return QueryService(
        ingestion=IngestionService(
            ticker_resolver=TickerResolver(),
            edgar_client=EdgarClient(),
            embeddings_client=OpenAIEmbeddingsClient(),
            parser=FilingParser(),
        ),
        retriever=HybridRetriever(OpenAIEmbeddingsClient()),
        synthesizer=Synthesizer(OpenAIChatClient()),
    )


@pytest.mark.eval
@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: f"{c['ticker']}-{c['question'][:40]}")
def test_eval_case(case):
    service = _service()
    result = asyncio.run(_run_case(service, case))
    # Soft assertions: we report metrics rather than fail on the first miss
    # so the whole grid runs even if a few cases regress. The aggregate
    # pass-rate threshold lives in `run_eval.py`.
    assert result.has_citations or not (case.get("expected_answer_contains")), (
        f"No citations produced for {case['ticker']}: {case['question']}"
    )
