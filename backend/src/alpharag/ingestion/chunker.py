"""Section -> chunks.

Each chunk:
- Stays within `chunk_size_tokens` (default 800), with `chunk_overlap_tokens`
  (default 100) of overlap to preserve context across boundaries.
- Carries char-offset metadata back to the section text (for citation spans).
- Has the section header (e.g. "Apple Inc. 10-K FY2024 / Item 1A. Risk
  Factors") prepended to the embedded text so retrieval matches header-only
  queries like "what risks does Apple call out?".

Token counting uses tiktoken (cl100k_base) which matches the OpenAI
embedding model's tokenizer.
"""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from alpharag.core.config import get_settings
from alpharag.ingestion.parser import ParsedSection

_ENCODER = tiktoken.get_encoding("cl100k_base")


@dataclass(frozen=True, slots=True)
class Chunk:
    section: ParsedSection
    chunk_index: int
    text: str  # raw chunk text (no header prefix)
    embed_text: str  # what we send to the embedder (header + text)
    char_start: int  # absolute offset in section.text
    char_end: int
    token_count: int


def chunk_section(
    section: ParsedSection,
    *,
    company_name: str,
    form_type: str,
    filing_date: str,
    chunk_size_tokens: int | None = None,
    chunk_overlap_tokens: int | None = None,
) -> list[Chunk]:
    settings = get_settings()
    target = chunk_size_tokens or settings.chunk_size_tokens
    overlap = chunk_overlap_tokens or settings.chunk_overlap_tokens
    if overlap >= target:
        overlap = target // 4

    header = _make_header(company_name, form_type, filing_date, section)

    text = section.text
    # Encode once, then walk by token windows. Map token offsets back to
    # char offsets via incremental decoding.
    tokens = _ENCODER.encode(text)
    if not tokens:
        return []

    chunks: list[Chunk] = []
    start_tok = 0
    chunk_index = 0
    char_cursor = 0  # tracks absolute position in `text` for the current window's start

    while start_tok < len(tokens):
        end_tok = min(start_tok + target, len(tokens))
        window_tokens = tokens[start_tok:end_tok]
        window_text = _ENCODER.decode(window_tokens)

        # Find this window in the original text starting from char_cursor to
        # avoid pathological matches earlier in the doc.
        idx = text.find(window_text[:80], char_cursor) if window_text else -1
        if idx == -1:
            # Fall back: use whatever we have; offsets will be approximate.
            idx = char_cursor
        char_start = idx
        char_end = char_start + len(window_text)
        char_end = min(char_end, len(text))

        chunk_text = text[char_start:char_end]
        embed_text = f"{header}\n\n{chunk_text}"
        chunks.append(
            Chunk(
                section=section,
                chunk_index=chunk_index,
                text=chunk_text,
                embed_text=embed_text,
                char_start=char_start,
                char_end=char_end,
                token_count=len(window_tokens),
            )
        )
        chunk_index += 1
        if end_tok == len(tokens):
            break
        start_tok = end_tok - overlap
        char_cursor = max(char_end - 200, 0)

    return chunks


def _make_header(
    company_name: str,
    form_type: str,
    filing_date: str,
    section: ParsedSection,
) -> str:
    bits: list[str] = [company_name]
    bits.append(f"{form_type} ({filing_date})")
    if section.item_code or section.title:
        bits.append(section.title)
    return " / ".join(bits)


def estimate_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))
