"""Prompts for the synthesizer.

Conventions:
- Each retrieved chunk is identified by `[c1]`, `[c2]`, ... and the model
  is required to cite chunks for every substantive claim using those
  markers in square brackets.
- Markers refer to the chunks the model was given, NOT to anything outside
  them. The post-processor in `citation_parser.py` enforces this.
"""

from __future__ import annotations

from dataclasses import dataclass

from alpharag.db.repositories.chunk_repo import HybridSearchHit


@dataclass(frozen=True, slots=True)
class PromptedContext:
    """A retrieved chunk with the marker we'll show the LLM."""

    marker: str  # "c1", "c2", ...
    hit: HybridSearchHit


SYSTEM_PROMPT = """You are AlphaRAG, a financial research assistant.

You answer questions about a single public company using ONLY the excerpts
from that company's SEC filings provided in the user's message. You never
use outside knowledge or facts not present in the excerpts.

Rules:
1. Every substantive claim in your answer MUST cite one or more excerpts
   using their marker, e.g. "[c1]" or "[c1][c3]". Place the markers
   inline, immediately after the claim they support.
2. If the excerpts do not contain enough information to answer the
   question, say so plainly. Do not guess. A short, honest "The provided
   filings do not address this" is better than speculation.
3. Quote sparingly. Paraphrase in clear, neutral prose.
4. Do not give investment advice or personal opinions.
5. Keep the answer focused. Aim for 2-5 short paragraphs unless the
   question genuinely requires more.
"""


def build_user_prompt(
    *,
    ticker: str,
    company_name: str,
    question: str,
    contexts: list[PromptedContext],
) -> str:
    if not contexts:
        return (
            f"Company: {company_name} ({ticker})\n\n"
            f"Question: {question}\n\n"
            "No excerpts were retrieved. Answer that the filings do not "
            "appear to address this question."
        )

    sections = []
    for ctx in contexts:
        h = ctx.hit
        header = f"[{ctx.marker}] {h.form_type} ({h.filing_date}) -- {h.section_title}"
        body = h.text.strip()
        sections.append(f"{header}\n{body}")
    excerpts_block = "\n\n---\n\n".join(sections)

    return (
        f"Company: {company_name} ({ticker})\n\n"
        f"Question: {question}\n\n"
        f"Excerpts from {ticker}'s SEC filings:\n\n"
        f"{excerpts_block}\n\n"
        f"Answer the question using ONLY these excerpts. Cite every claim "
        f"with the corresponding marker(s) in square brackets, e.g. [c1]."
    )


def assign_markers(hits: list[HybridSearchHit]) -> list[PromptedContext]:
    return [
        PromptedContext(marker=f"c{i + 1}", hit=h)
        for i, h in enumerate(hits)
    ]
