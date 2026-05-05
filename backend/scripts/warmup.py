"""Pre-warm the database by ingesting filings for one or more tickers.

Reuses the exact `IngestionService` used by the live query path. After
warmup, queries against these tickers hit the cache and return in seconds.

Usage:
    python -m scripts.warmup --tickers AAPL,MSFT,GOOGL,NVDA,TSLA
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from alpharag.core.logging import configure_logging, get_logger
from alpharag.db.session import dispose_engine, session_scope
from alpharag.ingestion.edgar_client import EdgarClient
from alpharag.ingestion.parser import FilingParser
from alpharag.ingestion.ticker_resolver import TickerResolver
from alpharag.llm import OpenAIEmbeddingsClient
from alpharag.services.ingestion_service import IngestionService


async def _warm_one(service: IngestionService, ticker: str, *, force: bool) -> None:
    log = get_logger("warmup")
    log.info("warmup_start", ticker=ticker)
    async with session_scope() as session:

        async def progress(stage: str, msg: str, data: dict) -> None:
            log.info("stage", stage=stage, msg=msg, **data)

        result = await service.ensure_ingested(
            session,
            ticker=ticker,
            force_refresh=force,
            progress=progress,
        )
        log.info(
            "warmup_done",
            ticker=ticker,
            cache_hit=result.cache_hit,
            filings=result.filings_ingested,
            chunks=result.chunks_created,
        )


async def _main(tickers: list[str], force: bool) -> int:
    configure_logging("INFO")
    service = IngestionService(
        ticker_resolver=TickerResolver(),
        edgar_client=EdgarClient(),
        embeddings_client=OpenAIEmbeddingsClient(),
        parser=FilingParser(),
    )
    failed: list[str] = []
    for t in tickers:
        try:
            await _warm_one(service, t.strip().upper(), force=force)
        except Exception as e:
            get_logger("warmup").error("warmup_failed", ticker=t, error=str(e))
            failed.append(t)
    await dispose_engine()
    if failed:
        sys.stderr.write(f"Failed to warm: {', '.join(failed)}\n")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-warm AlphaRAG with one or more tickers.")
    parser.add_argument(
        "--tickers",
        required=True,
        help="Comma-separated tickers, e.g. AAPL,MSFT,GOOGL",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-ingestion even if filings are fresh",
    )
    args = parser.parse_args()
    tickers = [t for t in args.tickers.split(",") if t.strip()]
    if not tickers:
        sys.stderr.write("No tickers provided.\n")
        sys.exit(2)
    sys.exit(asyncio.run(_main(tickers, args.refresh)))


if __name__ == "__main__":
    main()
