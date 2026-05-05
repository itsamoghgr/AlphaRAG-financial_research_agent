"""Unit tests for the freshness policy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from alpharag.db.models import Company
from alpharag.services.freshness_policy import evaluate_freshness


def _company(**kwargs) -> Company:
    return Company(
        ticker=kwargs.get("ticker", "AAPL"),
        cik=kwargs.get("cik", "0000320193"),
        name=kwargs.get("name", "Apple Inc."),
        last_ingested_at=kwargs.get("last_ingested_at"),
        last_ingest_status=kwargs.get("last_ingest_status"),
    )


def test_freshness_unknown_company_is_stale():
    decision = evaluate_freshness(None)
    assert not decision.is_fresh
    assert decision.reason == "company_not_seen"


def test_freshness_never_ingested_is_stale():
    decision = evaluate_freshness(_company())
    assert not decision.is_fresh
    assert decision.reason == "never_ingested"


def test_freshness_recent_success_is_fresh():
    c = _company(
        last_ingested_at=datetime.now(UTC) - timedelta(days=1),
        last_ingest_status="succeeded",
    )
    decision = evaluate_freshness(c)
    assert decision.is_fresh


def test_freshness_old_ingest_is_stale():
    c = _company(
        last_ingested_at=datetime.now(UTC) - timedelta(days=30),
        last_ingest_status="succeeded",
    )
    decision = evaluate_freshness(c)
    assert not decision.is_fresh
    assert decision.reason == "stale"


def test_freshness_failed_ingest_is_stale():
    c = _company(
        last_ingested_at=datetime.now(UTC),
        last_ingest_status="failed",
    )
    decision = evaluate_freshness(c)
    assert not decision.is_fresh
    assert decision.reason == "previous_ingest_failed"


def test_freshness_force_refresh_overrides():
    c = _company(
        last_ingested_at=datetime.now(UTC),
        last_ingest_status="succeeded",
    )
    decision = evaluate_freshness(c, force_refresh=True)
    assert not decision.is_fresh
    assert decision.reason == "refresh_requested"
