"""Batched embedding helper.

Wraps an `EmbeddingsClient` with concurrency control + batching. OpenAI's
limit is generous (8192 tokens per input, hundreds of inputs per request),
but we keep batches conservative so a single failure doesn't lose much work.
"""

from __future__ import annotations

from collections.abc import Sequence

from alpharag.llm.base import EmbeddingsClient

DEFAULT_BATCH_SIZE = 64


async def embed_in_batches(
    client: EmbeddingsClient,
    texts: Sequence[str],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[list[float]]:
    if not texts:
        return []
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = list(texts[i : i + batch_size])
        out.extend(await client.embed(batch))
    return out
