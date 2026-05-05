"""Shared response envelopes."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    db_connected: bool
