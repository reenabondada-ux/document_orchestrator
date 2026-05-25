"""FastAPI dependency providers for the Document Orchestrator API.

All heavyweight objects are obtained from ``app.state`` (populated once by the
lifespan context in ``app.py``).  Route handlers declare these as ``Depends()``
parameters and never instantiate connections or services themselves.

Override any provider in tests via ``app.dependency_overrides``::

    from mainframe_doc_orchestrator.api.dependencies import get_workflow
    app.dependency_overrides[get_workflow] = lambda: fake_workflow
"""
from __future__ import annotations

from fastapi import Depends, Request
from typing import Annotated

from mainframe_doc_orchestrator.persistence.repositories import PostgresDocumentRepository, RetrievalPassRepository
from mainframe_doc_orchestrator.services.exporter import DocumentExporter
from mainframe_doc_orchestrator.services.workflow_engine import DocumentWorkflowEngine


# ---------------------------------------------------------------------------
# Infrastructure providers — draw from app.state set by the lifespan
# ---------------------------------------------------------------------------

def get_pg_pool(request: Request):
    """Return the shared async Postgres connection pool from app.state."""
    return request.app.state.pg_pool


def get_llm_client(request: Request):
    """Return the shared LLM client from app.state."""
    return request.app.state.llm_client


def get_retrieval_client(request: Request):
    """Return the shared retrieval client from app.state."""
    return request.app.state.retrieval_client


# ---------------------------------------------------------------------------
# Repository providers — constructed per-request; pool is shared
# ---------------------------------------------------------------------------

def get_document_repository(
    pg_pool: Annotated[object, Depends(get_pg_pool)],
) -> PostgresDocumentRepository:
    """Return a PostgresDocumentRepository bound to the shared pool."""
    return PostgresDocumentRepository(pg_pool)


def get_retrieval_pass_repository(
    pg_pool: Annotated[object, Depends(get_pg_pool)],
) -> RetrievalPassRepository:
    """Return a RetrievalPassRepository bound to the shared pool."""
    return RetrievalPassRepository(pg_pool)


# ---------------------------------------------------------------------------
# Service provider — assembles DocumentWorkflowEngine from injected dependencies
# ---------------------------------------------------------------------------

def get_workflow(
    llm_client: Annotated[object, Depends(get_llm_client)],
    retrieval_client: Annotated[object, Depends(get_retrieval_client)],
    document_repository: Annotated[PostgresDocumentRepository, Depends(get_document_repository)],
    retrieval_pass_repository: Annotated[RetrievalPassRepository, Depends(get_retrieval_pass_repository)],
) -> DocumentWorkflowEngine:
    """Assemble and return a DocumentWorkflowEngine for the current request."""
    return DocumentWorkflowEngine(
        retrieval_client=retrieval_client,
        llm_client=llm_client,
        document_repository=document_repository,
        retrieval_pass_repository=retrieval_pass_repository,
        exporter=DocumentExporter(),
    )
