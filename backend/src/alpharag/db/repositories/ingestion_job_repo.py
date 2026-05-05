"""IngestionJob repository: tracks lifecycle of per-ticker ingestion runs."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from alpharag.db.models import IngestionJob


class IngestionJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start(self, *, company_id: UUID) -> IngestionJob:
        job = IngestionJob(company_id=company_id, status="running", stage="starting")
        self._session.add(job)
        await self._session.flush()
        return job

    async def update_stage(self, job_id: UUID, *, stage: str) -> None:
        job = await self._session.get(IngestionJob, job_id)
        if job is None:
            return
        job.stage = stage
        await self._session.flush()

    async def succeed(self, job_id: UUID, *, details: dict | None = None) -> None:
        job = await self._session.get(IngestionJob, job_id)
        if job is None:
            return
        job.status = "succeeded"
        job.stage = "done"
        job.finished_at = datetime.now(UTC)
        if details is not None:
            job.details = details
        await self._session.flush()

    async def fail(self, job_id: UUID, *, error: str) -> None:
        job = await self._session.get(IngestionJob, job_id)
        if job is None:
            return
        job.status = "failed"
        job.finished_at = datetime.now(UTC)
        job.error = error
        await self._session.flush()
