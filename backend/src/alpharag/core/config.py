"""Application configuration loaded from environment variables.

A single `Settings` instance is exposed via `get_settings()` and is cached for
the process lifetime.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://alpharag:alpharag@localhost:5432/alpharag"
    database_url_sync: str = "postgresql+psycopg://alpharag:alpharag@localhost:5432/alpharag"

    # LLM
    openai_api_key: str = Field(default="")
    llm_model: str = "gpt-4o-mini"
    llm_fallback_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # SEC EDGAR
    # NB: EDGAR's fair-access policy requires a User-Agent containing your contact email.
    sec_user_agent: str = "AlphaRAG Research alpharag@example.com"
    sec_requests_per_second: int = 8

    # Ingestion policy
    ingest_freshness_days: int = 7
    ingest_num_10k: int = 1
    ingest_num_10q: int = 2
    chunk_size_tokens: int = 800
    chunk_overlap_tokens: int = 100

    # Filesystem cache (raw EDGAR HTML, parsed sections)
    var_dir: Path = Path("var")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def edgar_cache_dir(self) -> Path:
        return self.var_dir / "cache" / "edgar"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
