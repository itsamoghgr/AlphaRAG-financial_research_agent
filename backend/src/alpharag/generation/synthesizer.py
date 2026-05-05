"""LLM synthesizer with mandatory citation enforcement.

If the model returns an answer with zero citation markers, we retry once
with a stricter system message. After two failed attempts we surface the
answer anyway with `missing_citations=True` so the API can decide how to
render it (typically: still show, but flag).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from alpharag.core.errors import LLMError
from alpharag.core.logging import get_logger
from alpharag.db.repositories.chunk_repo import HybridSearchHit
from alpharag.generation.citation_parser import (
    CitationParseResult,
    parse_citations,
)
from alpharag.generation.prompts import (
    SYSTEM_PROMPT,
    assign_markers,
    build_user_prompt,
)
from alpharag.llm.base import ChatClient, ChatMessage

logger = get_logger(__name__)

STRICT_RETRY_SUFFIX = (
    "\n\nIMPORTANT: Your previous answer did not cite any excerpts. You MUST "
    "include at least one [cN] marker for every claim. If the excerpts truly "
    "do not address the question, say so explicitly."
)


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    answer: str
    citations: CitationParseResult
    model: str
    prompt_tokens: int
    completion_tokens: int
    retried: bool


class Synthesizer:
    def __init__(self, chat: ChatClient) -> None:
        self._chat = chat

    async def synthesize(
        self,
        *,
        ticker: str,
        company_name: str,
        question: str,
        hits: list[HybridSearchHit],
    ) -> SynthesisResult:
        contexts = assign_markers(hits)
        user_msg = build_user_prompt(
            ticker=ticker,
            company_name=company_name,
            question=question,
            contexts=contexts,
        )
        result = await self._call(SYSTEM_PROMPT, user_msg, contexts)
        if not result.citations.missing_citations or not contexts:
            return result

        # Retry once with a strict reminder.
        logger.info("synth_retry_no_citations", ticker=ticker)
        retry_result = await self._call(
            SYSTEM_PROMPT + STRICT_RETRY_SUFFIX, user_msg, contexts
        )
        return SynthesisResult(
            answer=retry_result.answer,
            citations=retry_result.citations,
            model=retry_result.model,
            prompt_tokens=retry_result.prompt_tokens,
            completion_tokens=retry_result.completion_tokens,
            retried=True,
        )

    async def _call(
        self,
        system_prompt: str,
        user_prompt: str,
        contexts,
    ) -> SynthesisResult:
        try:
            completion = await self._chat.complete(
                [
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=user_prompt),
                ],
                temperature=0.0,
                max_tokens=900,
            )
        except LLMError:
            raise
        citations = parse_citations(answer=completion.text, contexts=contexts)
        return SynthesisResult(
            answer=completion.text,
            citations=citations,
            model=completion.model,
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            retried=False,
        )

    async def stream_synthesize(
        self,
        *,
        ticker: str,
        company_name: str,
        question: str,
        hits: list[HybridSearchHit],
    ) -> AsyncIterator[str]:
        """Token-streaming variant. Used by the SSE endpoint to forward
        deltas to the UI as they arrive. Citation parsing happens after
        streaming completes (the caller buffers the full answer)."""
        contexts = assign_markers(hits)
        user_msg = build_user_prompt(
            ticker=ticker,
            company_name=company_name,
            question=question,
            contexts=contexts,
        )
        async for delta in self._chat.stream(
            [
                ChatMessage(role="system", content=SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_msg),
            ],
            temperature=0.0,
            max_tokens=900,
        ):
            yield delta
