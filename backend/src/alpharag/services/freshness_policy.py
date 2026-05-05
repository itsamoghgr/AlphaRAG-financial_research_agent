"""Freshness policy: deciding whether a company's filings need a refresh.

MVP rule: a company is "fresh" if `last_ingested_at` is within
`INGEST_FRESHNESS_DAYS` (default 7). Otherwise we check EDGAR for any
filings newer than our latest stored `filing_date` and only ingest the delta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from alpharag.core.config import get_settings
from alpharag.db.models import Company


@dataclass(frozen=True, slots=True)
class FreshnessDecision:
    is_fresh: bool
    reason: str


def evaluate_freshness(company: Company | None, *, force_refresh: bool = False) -> FreshnessDecision:
    if force_refresh:
        return FreshnessDecision(False, "refresh_requested")
    if company is None:
        return FreshnessDecision(False, "company_not_seen")
    if company.last_ingested_at is None:
        return FreshnessDecision(False, "never_ingested")
    if company.last_ingest_status == "failed":
        return FreshnessDecision(False, "previous_ingest_failed")

    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(days=settings.ingest_freshness_days)
    last = company.last_ingested_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    if last < cutoff:
        return FreshnessDecision(False, "stale")
    return FreshnessDecision(True, "within_ttl")
