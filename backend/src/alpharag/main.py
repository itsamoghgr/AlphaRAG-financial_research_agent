"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from alpharag import __version__
from alpharag.api.routers import companies, filings, health, query
from alpharag.api.schemas.common import ErrorResponse
from alpharag.core.config import get_settings
from alpharag.core.errors import AlphaRAGError
from alpharag.core.logging import configure_logging, get_logger
from alpharag.db.session import dispose_engine

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("startup", env=settings.app_env, version=__version__)
    try:
        yield
    finally:
        await dispose_engine()
        logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AlphaRAG",
        version=__version__,
        description="Financial research agent over SEC filings.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(query.router)
    app.include_router(companies.router)
    app.include_router(filings.router)

    @app.exception_handler(AlphaRAGError)
    async def app_error_handler(_req: Request, exc: AlphaRAGError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                code=exc.code, message=exc.message, details=exc.details
            ).model_dump(),
        )

    return app


app = create_app()
