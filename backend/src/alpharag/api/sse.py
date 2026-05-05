"""Typed SSE event helpers.

The frontend relies on a stable event vocabulary; centralizing it here
makes the contract explicit.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# Stage names match the frontend's IngestionProgress component.
Stage = Literal[
    "resolving",
    "cache_hit",
    "fetching",
    "parsing",
    "chunking",
    "embedding",
    "persisting",
    "retrieving",
    "generating",
    "done",
    "error",
]


@dataclass(frozen=True, slots=True)
class StageEvent:
    stage: Stage
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> dict[str, str]:
        """Format for sse-starlette's EventSourceResponse."""
        return {
            "event": self.stage,
            "data": json.dumps({"message": self.message, **self.data}),
        }


@dataclass(frozen=True, slots=True)
class TokenEvent:
    """A single token (or text fragment) being streamed during generation."""

    text: str

    def to_sse(self) -> dict[str, str]:
        return {"event": "token", "data": json.dumps({"text": self.text})}


@dataclass(frozen=True, slots=True)
class FinalEvent:
    """Final payload: the full answer plus citations."""

    answer: str
    citations: list[dict[str, Any]]
    timings_ms: dict[str, int]

    def to_sse(self) -> dict[str, str]:
        return {"event": "done", "data": json.dumps(asdict(self))}


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    code: str
    message: str

    def to_sse(self) -> dict[str, str]:
        return {"event": "error", "data": json.dumps({"code": self.code, "message": self.message})}
