"""Unit tests for citation marker parsing."""

from __future__ import annotations

import uuid

from alpharag.db.repositories.chunk_repo import HybridSearchHit
from alpharag.generation.citation_parser import make_snippet, parse_citations
from alpharag.generation.prompts import assign_markers


def _hit(text: str = "x") -> HybridSearchHit:
    return HybridSearchHit(
        chunk_id=uuid.uuid4(),
        section_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        text=text,
        char_start=0,
        char_end=len(text),
        score=1.0,
        score_vector=1.0,
        score_fts=0.5,
        item_code="Item 1A",
        section_title="Item 1A. Risk Factors",
        filing_id=uuid.uuid4(),
        form_type="10-K",
        filing_date="2024-09-30",
        accession_no="0000320193-24-000123",
        source_url="https://www.sec.gov/example",
    )


def test_parse_citations_resolves_known_markers():
    contexts = assign_markers([_hit("a"), _hit("b"), _hit("c")])
    answer = "Apple is a company [c1]. It sells phones [c2][c3]."
    result = parse_citations(answer=answer, contexts=contexts)
    assert result.used_markers == ["c1", "c2", "c3"]
    assert [r.marker for r in result.resolved] == ["c1", "c2", "c3"]
    assert result.unknown_markers == []
    assert not result.missing_citations


def test_parse_citations_flags_unknown_markers():
    contexts = assign_markers([_hit("a")])
    answer = "Some claim [c1]. Another claim [c5]."
    result = parse_citations(answer=answer, contexts=contexts)
    assert result.used_markers == ["c1", "c5"]
    assert [r.marker for r in result.resolved] == ["c1"]
    assert result.unknown_markers == ["c5"]


def test_parse_citations_missing():
    contexts = assign_markers([_hit("a")])
    answer = "An answer with no markers at all."
    result = parse_citations(answer=answer, contexts=contexts)
    assert result.missing_citations
    assert result.resolved == []


def test_make_snippet_truncates():
    snippet = make_snippet("hello " * 200, max_chars=50)
    assert len(snippet) <= 53  # 50 + "..."
    assert snippet.endswith("...")


def test_make_snippet_collapses_whitespace():
    snippet = make_snippet("hello\n\n  world\t\tfoo")
    assert snippet == "hello world foo"
