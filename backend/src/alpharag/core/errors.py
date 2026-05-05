"""Typed application exceptions.

Each exception carries enough context for the API layer to produce a useful
HTTP response without leaking internals.
"""

from __future__ import annotations


class AlphaRAGError(Exception):
    """Base class for all expected, typed application errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UnknownTickerError(AlphaRAGError):
    status_code = 404
    code = "unknown_ticker"


class NoFilingsFoundError(AlphaRAGError):
    status_code = 404
    code = "no_filings_found"


class IngestionError(AlphaRAGError):
    status_code = 502
    code = "ingestion_failed"


class EdgarRateLimitError(AlphaRAGError):
    status_code = 503
    code = "edgar_rate_limited"


class CitationValidationError(AlphaRAGError):
    status_code = 502
    code = "citation_validation_failed"


class LLMError(AlphaRAGError):
    status_code = 502
    code = "llm_error"
