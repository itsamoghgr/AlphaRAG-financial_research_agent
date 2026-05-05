"""Run a hybrid search against an already-ingested ticker, without an LLM.

Useful for tuning retrieval parameters and debugging the chunker without
spending API tokens.

Usage:
    python -m scripts.search --ticker AAPL "what risk factors does the company face"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID

from alpharag.core.errors import UnknownTickerError
from alpharag.core.logging import configure_logging, get_logger
from alpharag.db.repositories.company_repo import CompanyRepository
from alpharag.db.session import dispose_engine, session_scope
from alpharag.ingestion.ticker_resolver import TickerResolver
from alpharag.llm import OpenAIEmbeddingsClient
from alpharag.retrieval.hybrid import HybridRetriever


async def _main(ticker: str, query: str, top_k: int) -> int:
    configure_logging("WARNING")  # quiet -- we want clean stdout for results
    log = get_logger("search")
    resolver = TickerResolver()
    embeddings = OpenAIEmbeddingsClient()
    retriever = HybridRetriever(embeddings)

    try:
        info = await resolver.resolve(ticker)
    except UnknownTickerError as e:
        log.error("unknown_ticker", ticker=ticker, message=e.message)
        return 1

    async with session_scope() as session:
        company = await CompanyRepository(session).get_by_cik(info.cik)
        if company is None:
            sys.stderr.write(
                f"{ticker} has not been ingested. Run: python -m scripts.warmup --tickers {ticker}\n"
            )
            return 1
        result = await retriever.retrieve(
            session,
            company_id=UUID(str(company.id)),
            query=query,
            top_k=top_k,
        )

    print(f"\nQuery: {query}")
    print(f"Ticker: {info.ticker}  CIK: {info.cik}\n")
    if not result.hits:
        print("No hits.")
        return 0
    for i, hit in enumerate(result.hits, 1):
        print(f"--- [{i}] score={hit.score:.4f} (vec={hit.score_vector:.3f} fts={hit.score_fts:.3f}) ---")
        print(f"  {hit.form_type} {hit.filing_date} -- {hit.section_title}")
        snippet = hit.text.strip().replace("\n", " ")
        if len(snippet) > 280:
            snippet = snippet[:280] + "..."
        print(f"  {snippet}\n")
    await dispose_engine()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug hybrid retrieval against an ingested ticker.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("query", nargs="+", help="The search query")
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args.ticker, " ".join(args.query), args.top_k)))


if __name__ == "__main__":
    main()
