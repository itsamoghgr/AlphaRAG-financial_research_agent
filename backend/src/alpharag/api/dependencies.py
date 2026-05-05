"""FastAPI dependency providers.

Exposes per-request DB sessions, singleton LLM clients, and singleton
service-layer objects (which are cheap to construct and stateless). Routers
depend on these via the modern `Annotated` injection pattern:

    async def my_handler(session: SessionDep, query: QueryServiceDep) -> ...
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from alpharag.db.session import get_sessionmaker
from alpharag.generation.synthesizer import Synthesizer
from alpharag.ingestion.edgar_client import EdgarClient
from alpharag.ingestion.parser import FilingParser
from alpharag.ingestion.ticker_resolver import TickerResolver
from alpharag.llm import OpenAIChatClient, OpenAIEmbeddingsClient
from alpharag.llm.base import ChatClient, EmbeddingsClient
from alpharag.retrieval.hybrid import HybridRetriever
from alpharag.services.ingestion_service import IngestionService
from alpharag.services.query_service import QueryService


async def get_db_session() -> AsyncIterator[AsyncSession]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@lru_cache(maxsize=1)
def _chat_client_singleton() -> ChatClient:
    return OpenAIChatClient()


@lru_cache(maxsize=1)
def _embeddings_client_singleton() -> EmbeddingsClient:
    return OpenAIEmbeddingsClient()


@lru_cache(maxsize=1)
def _ticker_resolver_singleton() -> TickerResolver:
    return TickerResolver()


@lru_cache(maxsize=1)
def _edgar_client_singleton() -> EdgarClient:
    return EdgarClient()


@lru_cache(maxsize=1)
def _ingestion_service_singleton() -> IngestionService:
    return IngestionService(
        ticker_resolver=_ticker_resolver_singleton(),
        edgar_client=_edgar_client_singleton(),
        embeddings_client=_embeddings_client_singleton(),
        parser=FilingParser(),
    )


@lru_cache(maxsize=1)
def _retriever_singleton() -> HybridRetriever:
    return HybridRetriever(_embeddings_client_singleton())


@lru_cache(maxsize=1)
def _synthesizer_singleton() -> Synthesizer:
    return Synthesizer(_chat_client_singleton())


@lru_cache(maxsize=1)
def _query_service_singleton() -> QueryService:
    return QueryService(
        ingestion=_ingestion_service_singleton(),
        retriever=_retriever_singleton(),
        synthesizer=_synthesizer_singleton(),
    )


def get_chat_client() -> ChatClient:
    return _chat_client_singleton()


def get_embeddings_client() -> EmbeddingsClient:
    return _embeddings_client_singleton()


def get_ticker_resolver() -> TickerResolver:
    return _ticker_resolver_singleton()


def get_ingestion_service() -> IngestionService:
    return _ingestion_service_singleton()


def get_query_service() -> QueryService:
    return _query_service_singleton()


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
ChatClientDep = Annotated[ChatClient, Depends(get_chat_client)]
EmbeddingsClientDep = Annotated[EmbeddingsClient, Depends(get_embeddings_client)]
TickerResolverDep = Annotated[TickerResolver, Depends(get_ticker_resolver)]
IngestionServiceDep = Annotated[IngestionService, Depends(get_ingestion_service)]
QueryServiceDep = Annotated[QueryService, Depends(get_query_service)]
