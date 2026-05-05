"""Hybrid retriever: embed query, run hybrid SQL, return ranked hits.

The actual SQL fusion lives in `chunk_repo.hybrid_search`. This wrapper:
- enforces the mandatory `company_id` filter at the type level (we never
  expose an unscoped search API)
- handles query embedding
- exposes the ranking weights as parameters so they can be tuned without
  editing SQL
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from alpharag.db.repositories.chunk_repo import ChunkRepository, HybridSearchHit
from alpharag.llm.base import EmbeddingsClient


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    hits: list[HybridSearchHit]
    query_embedding_tokens: int  # informational, for cost tracking


class HybridRetriever:
    def __init__(self, embeddings_client: EmbeddingsClient) -> None:
        self._embeddings = embeddings_client

    async def retrieve(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        query: str,
        top_k: int = 8,
        vector_weight: float = 0.7,
        fts_weight: float = 0.3,
    ) -> RetrievalResult:
        if not query.strip():
            return RetrievalResult(hits=[], query_embedding_tokens=0)

        embeddings = await self._embeddings.embed([query])
        if not embeddings:
            return RetrievalResult(hits=[], query_embedding_tokens=0)
        query_vec = embeddings[0]

        chunk_repo = ChunkRepository(session)
        hits = await chunk_repo.hybrid_search(
            company_id=company_id,
            query_embedding=query_vec,
            query_text=query,
            top_k=top_k,
            vector_weight=vector_weight,
            fts_weight=fts_weight,
        )
        return RetrievalResult(hits=hits, query_embedding_tokens=0)
