"""Ticker -> CIK resolver, backed by a daily cache of EDGAR's
`company_tickers.json` file.

EDGAR publishes a free public mapping of every ticker to its 10-digit CIK at
<https://www.sec.gov/files/company_tickers.json>. We download it once and
refresh once per day; resolution is then a dict lookup.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from alpharag.core.config import get_settings
from alpharag.core.errors import UnknownTickerError
from alpharag.core.logging import get_logger

logger = get_logger(__name__)

EDGAR_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 1 day


@dataclass(frozen=True, slots=True)
class TickerInfo:
    ticker: str
    cik: str  # 10-digit zero-padded
    name: str


class TickerResolver:
    def __init__(self, *, cache_path: Path | None = None) -> None:
        settings = get_settings()
        self._cache_path = cache_path or (
            settings.var_dir / "cache" / "company_tickers.json"
        )
        self._user_agent = settings.sec_user_agent
        self._lock = asyncio.Lock()
        self._index: dict[str, TickerInfo] | None = None

    async def resolve(self, ticker: str) -> TickerInfo:
        index = await self._get_index()
        info = index.get(ticker.strip().upper())
        if info is None:
            raise UnknownTickerError(
                f"No CIK found for ticker '{ticker}'",
                details={"ticker": ticker},
            )
        return info

    async def _get_index(self) -> dict[str, TickerInfo]:
        async with self._lock:
            if self._index is not None and not self._cache_stale():
                return self._index
            raw = await self._load_or_fetch()
            self._index = self._build_index(raw)
            return self._index

    def _cache_stale(self) -> bool:
        if not self._cache_path.exists():
            return True
        age = time.time() - self._cache_path.stat().st_mtime
        return age > CACHE_TTL_SECONDS

    async def _load_or_fetch(self) -> dict:
        if not self._cache_stale():
            try:
                return json.loads(self._cache_path.read_text("utf-8"))
            except Exception as e:
                logger.warning("ticker_cache_corrupt", error=str(e))
        # Need to refresh
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": self._user_agent, "Accept": "application/json"},
        ) as client:
            resp = await client.get(EDGAR_TICKERS_URL)
            resp.raise_for_status()
            data = resp.json()
        self._cache_path.write_text(json.dumps(data), encoding="utf-8")
        logger.info("ticker_cache_refreshed", count=len(data))
        return data

    @staticmethod
    def _build_index(raw: dict) -> dict[str, TickerInfo]:
        # The file is shaped like {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
        index: dict[str, TickerInfo] = {}
        for entry in raw.values():
            try:
                ticker = str(entry["ticker"]).upper()
                cik = str(entry["cik_str"]).zfill(10)
                name = str(entry["title"])
            except (KeyError, TypeError, ValueError):
                continue
            index[ticker] = TickerInfo(ticker=ticker, cik=cik, name=name)
        return index
