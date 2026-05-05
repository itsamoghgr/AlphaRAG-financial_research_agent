"""Unit tests for the section-aware chunker."""

from __future__ import annotations

from itertools import pairwise

from alpharag.ingestion.chunker import chunk_section, estimate_tokens
from alpharag.ingestion.parser import ParsedSection


def _make_section(text: str) -> ParsedSection:
    return ParsedSection(
        item_code="Item 1A",
        title="Item 1A. Risk Factors",
        char_start=0,
        char_end=len(text),
        text=text,
    )


def test_chunker_emits_overlapping_chunks():
    body = "Sentence about something interesting. " * 600  # ~3000 tokens
    section = _make_section(body)
    chunks = chunk_section(
        section,
        company_name="Acme Corp",
        form_type="10-K",
        filing_date="2024-01-31",
        chunk_size_tokens=400,
        chunk_overlap_tokens=50,
    )
    assert len(chunks) >= 4
    # All chunks should be under (or close to) the target token count.
    for c in chunks:
        assert c.token_count <= 420  # small slack for tokenizer rounding
    # Chunks should be ordered and have overlapping char ranges.
    for prev, cur in pairwise(chunks):
        assert cur.chunk_index == prev.chunk_index + 1
        assert cur.char_start <= prev.char_end


def test_chunker_prepends_header_to_embed_text():
    body = "Some risk discussion text. " * 100
    section = _make_section(body)
    chunks = chunk_section(
        section,
        company_name="Apple Inc.",
        form_type="10-K",
        filing_date="2024-09-30",
    )
    assert chunks
    header_line = chunks[0].embed_text.splitlines()[0]
    assert "Apple Inc." in header_line
    assert "10-K" in header_line
    assert "Item 1A" in header_line


def test_chunker_returns_empty_on_empty_input():
    section = _make_section("")
    assert chunk_section(
        section,
        company_name="Acme",
        form_type="10-K",
        filing_date="2024-01-01",
    ) == []


def test_estimate_tokens_is_reasonable():
    assert estimate_tokens("hello world") < 10
    assert estimate_tokens("hello " * 1000) > 800
