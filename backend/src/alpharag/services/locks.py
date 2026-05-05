"""Per-CIK Postgres advisory locks.

We use `pg_advisory_xact_lock(key)` so the lock is held only for the duration
of the transaction holding the SQLAlchemy session. The key is a 64-bit hash
of "ingest:<cik>" derived from Postgres's own `hashtextextended`.

This serializes concurrent first-queries on the same ticker: the second
caller waits inside Postgres, then sees the cache hit when it acquires the
lock and re-checks freshness.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def acquire_ingestion_lock(session: AsyncSession, *, cik: str) -> None:
    """Acquire the per-CIK ingestion advisory lock for the current transaction.

    Blocks until the lock is granted. Released automatically at COMMIT/ROLLBACK.
    """
    sql = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")
    await session.execute(sql, {"key": f"ingest:{cik}"})


async def try_acquire_ingestion_lock(session: AsyncSession, *, cik: str) -> bool:
    """Non-blocking variant. Returns True if the lock was granted, else False.

    Useful when we want to skip ingestion if another worker is already doing it.
    """
    sql = text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))")
    result = await session.execute(sql, {"key": f"ingest:{cik}"})
    return bool(result.scalar_one())
