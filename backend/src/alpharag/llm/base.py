"""Provider-agnostic protocols for chat and embedding clients.

Anything in `services/`, `generation/`, or `ingestion/` should depend on
these protocols, not on `openai_provider`. This keeps the door open for
swapping in Anthropic / Ollama / Bedrock later.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True, slots=True)
class ChatCompletion:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int


class ChatClient(Protocol):
    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> ChatCompletion: ...

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]: ...


class EmbeddingsClient(Protocol):
    async def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]: ...

    @property
    def dimensions(self) -> int: ...
