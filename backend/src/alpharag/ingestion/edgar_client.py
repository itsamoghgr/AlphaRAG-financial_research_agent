"""SEC EDGAR async client.

EDGAR's fair-access policy:
- All requests must include a `User-Agent` containing your contact email.
- Sustained > 10 req/s will get you blocked. We default to a tighter 8 req/s
  with a token-bucket-style asyncio semaphore + sleep.

Endpoints used:
- `https://data.sec.gov/submissions/CIK{padded}.json` -- per-issuer filing index.
- `https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_nodashes}/{primary_document}`
  -- the actual filing document HTML.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from alpharag.core.config import get_settings
from alpharag.core.errors import EdgarRateLimitError, IngestionError
from alpharag.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FilingMetadata:
    accession_no: str  # e.g. "0000320193-24-000123"
    form_type: str  # "10-K", "10-Q"
    filing_date: date
    period_of_report: date | None
    primary_document: str  # filename within the accession
    source_url: str  # canonical SEC URL for the document


class _RateLimiter:
    """Simple async sliding-window rate limiter."""

    def __init__(self, requests_per_second: int) -> None:
        self._min_interval = 1.0 / max(requests_per_second, 1)
        self._lock = asyncio.Lock()
        self._last_at = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_at = time.monotonic()


class EdgarClient:
    SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        requests_per_second: int | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        settings = get_settings()
        self._user_agent = user_agent or settings.sec_user_agent
        self._rate_limiter = _RateLimiter(
            requests_per_second or settings.sec_requests_per_second
        )
        self._cache_dir = cache_dir or settings.edgar_cache_dir

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(EdgarRateLimitError),
    )
    async def _get(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        await self._rate_limiter.acquire()
        resp = await client.get(url)
        if resp.status_code == 429:
            raise EdgarRateLimitError(f"EDGAR rate limited at {url}")
        resp.raise_for_status()
        return resp

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=60.0,
            headers={
                "User-Agent": self._user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": "www.sec.gov",
            },
            follow_redirects=True,
        )

    async def list_filings(
        self,
        *,
        cik: str,
        form_types: list[str],
        max_per_form: dict[str, int],
    ) -> list[FilingMetadata]:
        """Return the latest N filings for each requested form type.

        EDGAR's submissions JSON contains parallel arrays keyed by index.
        """
        url = self.SUBMISSIONS_URL.format(cik=cik)
        async with self._client() as client:
            client.headers["Host"] = "data.sec.gov"
            resp = await self._get(client, url)
            payload = resp.json()

        recent = payload.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accession_nos = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        periods = recent.get("periodOfReport", [])
        primary_docs = recent.get("primaryDocument", [])
        if not (
            len(forms)
            == len(accession_nos)
            == len(filing_dates)
            == len(primary_docs)
        ):
            raise IngestionError("EDGAR submissions JSON arrays misaligned")

        cik_int = int(cik)
        out: list[FilingMetadata] = []
        counts: dict[str, int] = {ft: 0 for ft in form_types}
        for i, form in enumerate(forms):
            if form not in form_types:
                continue
            cap = max_per_form.get(form, 0)
            if counts[form] >= cap:
                continue
            accession = accession_nos[i]
            primary_doc = primary_docs[i]
            if not accession or not primary_doc:
                continue
            accession_nodashes = accession.replace("-", "")
            source_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik_int}/{accession_nodashes}/{primary_doc}"
            )
            out.append(
                FilingMetadata(
                    accession_no=accession,
                    form_type=form,
                    filing_date=date.fromisoformat(filing_dates[i]),
                    period_of_report=(
                        date.fromisoformat(periods[i])
                        if i < len(periods) and periods[i]
                        else None
                    ),
                    primary_document=primary_doc,
                    source_url=source_url,
                )
            )
            counts[form] += 1
            if all(counts[ft] >= max_per_form.get(ft, 0) for ft in form_types):
                break
        return out

    async def fetch_filing_html(
        self,
        *,
        cik: str,
        filing: FilingMetadata,
    ) -> tuple[str, Path]:
        """Download (or serve from disk cache) the filing's primary HTML document.

        Returns (html_text, cache_path).
        """
        accession_nodashes = filing.accession_no.replace("-", "")
        cache_path = (
            self._cache_dir
            / cik
            / accession_nodashes
            / filing.primary_document
        )
        if cache_path.exists():
            return cache_path.read_text("utf-8", errors="ignore"), cache_path

        async with self._client() as client:
            resp = await self._get(client, filing.source_url)
            text = resp.text

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
        return text, cache_path

    async def get_company_metadata(self, *, cik: str) -> dict:
        """Returns a small subset of fields we care about from the
        submissions JSON.
        """
        url = self.SUBMISSIONS_URL.format(cik=cik)
        async with self._client() as client:
            client.headers["Host"] = "data.sec.gov"
            resp = await self._get(client, url)
            payload = resp.json()
        return {
            "name": payload.get("name"),
            "sic": payload.get("sic"),
            "sicDescription": payload.get("sicDescription"),
            "fiscalYearEnd": payload.get("fiscalYearEnd"),
            "exchanges": payload.get("exchanges", []),
        }
