"""Chunk repository: bulk insert and hybrid vector + FTS search.

This repo is the single place that issues vector queries. Anywhere in the
codebase that needs "find me chunks similar to this query for ticker X" must
go through `hybrid_search` here.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from alpharag.db.models import Chunk


@dataclass(frozen=True, slots=True)
class ChunkInsert:
    section_id: UUID
    company_id: UUID
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    token_count: int
    embedding: list[float]


@dataclass(frozen=True, slots=True)
class HybridSearchHit:
    chunk_id: UUID
    section_id: UUID
    company_id: UUID
    text: str
    char_start: int
    char_end: int
    score: float
    score_vector: float
    score_fts: float
    # Joined metadata for citation rendering
    item_code: str | None
    section_title: str
    filing_id: UUID
    form_type: str
    filing_date: str  # ISO
    accession_no: str
    source_url: str


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_insert(self, chunks: list[ChunkInsert]) -> None:
        if not chunks:
            return
        objs = [
            Chunk(
                section_id=c.section_id,
                company_id=c.company_id,
                chunk_index=c.chunk_index,
                text=c.text,
                char_start=c.char_start,
                char_end=c.char_end,
                token_count=c.token_count,
                embedding=c.embedding,
            )
            for c in chunks
        ]
        self._session.add_all(objs)
        await self._session.flush()

    async def hybrid_search(
        self,
        *,
        company_id: UUID,
        query_embedding: list[float],
        query_text: str,
        top_k: int = 8,
        vector_weight: float = 0.7,
        fts_weight: float = 0.3,
    ) -> list[HybridSearchHit]:
        """Run a fused vector + FTS query, scoped to a single company.

        Returns the top_k chunks ranked by `vector_weight * cosine_sim +
        fts_weight * normalized_bm25`, joined with section + filing metadata
        for citation rendering.
        """
        sql = text(
            """
            WITH vec AS (
                SELECT
                    c.id AS chunk_id,
                    1 - (c.embedding <=> CAST(:embedding AS vector)) AS score_vector
                FROM chunks c
                WHERE c.company_id = :company_id
                ORDER BY c.embedding <=> CAST(:embedding AS vector)
                LIMIT :candidate_pool
            ),
            kw AS (
                SELECT
                    c.id AS chunk_id,
                    ts_rank_cd(
                        to_tsvector('english', c.text),
                        plainto_tsquery('english', :query_text)
                    ) AS score_fts_raw
                FROM chunks c
                WHERE c.company_id = :company_id
                  AND to_tsvector('english', c.text) @@ plainto_tsquery('english', :query_text)
                ORDER BY score_fts_raw DESC
                LIMIT :candidate_pool
            ),
            fused AS (
                SELECT
                    COALESCE(vec.chunk_id, kw.chunk_id) AS chunk_id,
                    COALESCE(vec.score_vector, 0)        AS score_vector,
                    COALESCE(kw.score_fts_raw, 0)        AS score_fts_raw
                FROM vec
                FULL OUTER JOIN kw ON vec.chunk_id = kw.chunk_id
            ),
            normed AS (
                SELECT
                    chunk_id,
                    score_vector,
                    CASE
                        WHEN MAX(score_fts_raw) OVER () = 0 THEN 0
                        ELSE score_fts_raw / MAX(score_fts_raw) OVER ()
                    END AS score_fts
                FROM fused
            )
            SELECT
                c.id            AS chunk_id,
                c.section_id,
                c.company_id,
                c.text,
                c.char_start,
                c.char_end,
                (:vector_weight * n.score_vector + :fts_weight * n.score_fts) AS score,
                n.score_vector,
                n.score_fts,
                s.item_code,
                s.title         AS section_title,
                s.filing_id,
                f.form_type,
                f.filing_date::text AS filing_date,
                f.accession_no,
                f.source_url
            FROM normed n
            JOIN chunks   c ON c.id = n.chunk_id
            JOIN sections s ON s.id = c.section_id
            JOIN filings  f ON f.id = s.filing_id
            ORDER BY score DESC
            LIMIT :top_k
            """
        ).bindparams(
            bindparam("embedding"),
            bindparam("company_id"),
            bindparam("query_text"),
            bindparam("top_k"),
            bindparam("candidate_pool"),
            bindparam("vector_weight"),
            bindparam("fts_weight"),
        )
        # asyncpg has no built-in codec for pgvector, so the SQL CASTs a text
        # literal: `CAST(:embedding AS vector)`. Send the embedding as the
        # pgvector text form ('[0.1,0.2,...]') rather than a Python list.
        embedding_literal = "[" + ",".join(repr(float(x)) for x in query_embedding) + "]"
        result = await self._session.execute(
            sql,
            {
                "embedding": embedding_literal,
                "company_id": company_id,
                "query_text": query_text,
                "top_k": top_k,
                "candidate_pool": max(top_k * 4, 32),
                "vector_weight": vector_weight,
                "fts_weight": fts_weight,
            },
        )
        return [
            HybridSearchHit(
                chunk_id=row["chunk_id"],
                section_id=row["section_id"],
                company_id=row["company_id"],
                text=row["text"],
                char_start=row["char_start"],
                char_end=row["char_end"],
                score=float(row["score"]),
                score_vector=float(row["score_vector"]),
                score_fts=float(row["score_fts"]),
                item_code=row["item_code"],
                section_title=row["section_title"],
                filing_id=row["filing_id"],
                form_type=row["form_type"],
                filing_date=row["filing_date"],
                accession_no=row["accession_no"],
                source_url=row["source_url"],
            )
            for row in result.mappings().all()
        ]
