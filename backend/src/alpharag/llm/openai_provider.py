"""OpenAI implementation of the LLM and embedding protocols.

Uses the async `openai` SDK. Retries are configured at the SDK level
(max_retries=2) with additional backoff on rate limits via tenacity.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from alpharag.core.config import get_settings
from alpharag.core.errors import LLMError
from alpharag.llm.base import ChatCompletion, ChatMessage


def _client() -> AsyncOpenAI:
    settings = get_settings()
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-replace"):
        raise LLMError("OPENAI_API_KEY is not configured")
    return AsyncOpenAI(api_key=settings.openai_api_key, max_retries=2)


class OpenAIChatClient:
    def __init__(self, default_model: str | None = None) -> None:
        self._default_model = default_model or get_settings().llm_model

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(LLMError),
    )
    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> ChatCompletion:
        client = _client()
        try:
            resp = await client.chat.completions.create(
                model=model or self._default_model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            raise LLMError(f"OpenAI chat call failed: {e}") from e

        choice = resp.choices[0]
        usage = resp.usage
        return ChatCompletion(
            text=choice.message.content or "",
            model=resp.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        client = _client()
        try:
            stream = await client.chat.completions.create(
                model=model or self._default_model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
        except Exception as e:
            raise LLMError(f"OpenAI streaming call failed: {e}") from e

        async for event in stream:
            if not event.choices:
                continue
            delta = event.choices[0].delta.content
            if delta:
                yield delta


class OpenAIEmbeddingsClient:
    def __init__(self, default_model: str | None = None) -> None:
        settings = get_settings()
        self._default_model = default_model or settings.embedding_model
        self._dimensions = settings.embedding_dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(LLMError),
    )
    async def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        if not texts:
            return []
        client = _client()
        try:
            resp = await client.embeddings.create(
                model=model or self._default_model,
                input=list(texts),
            )
        except Exception as e:
            raise LLMError(f"OpenAI embeddings call failed: {e}") from e
        return [d.embedding for d in resp.data]
