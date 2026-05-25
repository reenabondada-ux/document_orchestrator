"""Application factory for the Mainframe Document Orchestrator API.

Shared resources are created exactly once during startup via a FastAPI lifespan
context and torn down cleanly on shutdown:

  - ``psycopg_pool.AsyncConnectionPool`` — Postgres connection pool (min 2, max 10).
  - LLM client (echo / OpenAI-compatible / Bedrock) — built from settings.
  - Retrieval client (HTTP / stub) — built from settings.

Dependency wiring lives entirely in ``api/dependencies.py``.
Route handlers live entirely in ``api/routes/documents.py``.

Usage (Uvicorn)::

    uvicorn mainframe_doc_orchestrator.api.app:app --host 0.0.0.0 --port 8002
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from mainframe_doc_orchestrator.settings import Settings, get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Open shared I/O resources before the first request; close after the last."""
    import psycopg_pool

    from mainframe_doc_orchestrator.clients.llm_clients import llm_client_from_settings
    from mainframe_doc_orchestrator.clients.retrieval_client import (
        retrieval_client_from_settings,
    )

    settings: Settings = app.state.settings
    logger.info("Document Orchestrator API: starting up")

    # Postgres async connection pool — shared across all requests.
    pg_pool = psycopg_pool.AsyncConnectionPool(
        settings.postgres_dsn,
        min_size=2,
        max_size=10,
        open=False,
    )
    await pg_pool.open()

    # LLM and retrieval clients — provider selection and validation live in the
    # respective client modules; lifespan only calls the factory functions.
    llm_client = llm_client_from_settings(settings)
    retrieval_client = retrieval_client_from_settings(settings)

    app.state.pg_pool = pg_pool
    app.state.llm_client = llm_client
    app.state.retrieval_client = retrieval_client

    yield

    logger.info("Document Orchestrator API: shutting down")
    await pg_pool.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Return a fully configured FastAPI application.

    Separated from the module-level ``app`` instance so tests can call
    ``create_app()``, apply ``dependency_overrides``, and then start the
    lifespan independently.
    """
    resolved = settings or get_settings()
    app = FastAPI(
        title=resolved.app_name,
        version="0.2.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved
    from mainframe_doc_orchestrator.api.routes.documents import (
        router as documents_router,
    )  # local import avoids circular init

    app.include_router(documents_router)
    return app


app = create_app()
