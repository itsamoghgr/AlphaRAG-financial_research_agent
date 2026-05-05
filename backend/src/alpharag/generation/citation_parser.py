"""Validates and resolves [cN] citation markers produced by the LLM.

Two responsibilities:
1. Extract every marker the model emitted (e.g. [c1], [c1][c3]).
2. Verify each marker maps to one of the chunks we actually showed the
   model. Markers that point to non-existent chunks are dropped (not
   silently — a warning is logged so we can tighten the prompt later).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from alpharag.core.logging import get_logger
from alpharag.generation.prompts import PromptedContext

logger = get_logger(__name__)

MARKER_RE = re.compile(r"\[c(\d+)\]")


@dataclass(frozen=True, slots=True)
class ResolvedCitation:
    marker: str  # "c1"
    context: PromptedContext


@dataclass(frozen=True, slots=True)
class CitationParseResult:
    used_markers: list[str]  # in order of first appearance
    resolved: list[ResolvedCitation]
    unknown_markers: list[str]
    missing_citations: bool  # True if no markers at all


def parse_citations(
    *,
    answer: str,
    contexts: list[PromptedContext],
) -> CitationParseResult:
    by_marker = {ctx.marker: ctx for ctx in contexts}

    seen: list[str] = []
    seen_set: set[str] = set()
    unknown: list[str] = []
    for m in MARKER_RE.finditer(answer):
        marker = f"c{m.group(1)}"
        if marker in seen_set:
            continue
        seen.append(marker)
        seen_set.add(marker)
        if marker not in by_marker:
            unknown.append(marker)

    resolved = [
        ResolvedCitation(marker=marker, context=by_marker[marker])
        for marker in seen
        if marker in by_marker
    ]

    if unknown:
        logger.warning(
            "citation_unknown_markers",
            unknown=unknown,
            available=sorted(by_marker.keys()),
        )

    return CitationParseResult(
        used_markers=seen,
        resolved=resolved,
        unknown_markers=unknown,
        missing_citations=len(seen) == 0,
    )


def make_snippet(text: str, *, max_chars: int = 280) -> str:
    text = text.strip().replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."
