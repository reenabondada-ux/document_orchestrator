"""FastAPI route handlers for the Document Orchestrator API.

All handlers are ``async def`` and declare their dependencies via ``Depends()``.
No handler reaches into ``request.app.state`` directly — all wiring lives in
``api/dependencies.py``.

Override any dependency in tests via ``app.dependency_overrides``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from mainframe_doc_orchestrator.api.dependencies import get_workflow
from mainframe_doc_orchestrator.api.schemas import (
    ApproveSectionRequest,
    COMPLEXITY_RETRIEVAL_PARAMS,
    DocumentCreateRequest,
    DocumentRunResponse,
    ExportRequest,
    ExportResponse,
    GenerateRequest,
    RetrievalPassResponse,
    SectionResponse,
)
from mainframe_doc_orchestrator.models import (
    DocumentRequest,
)
from mainframe_doc_orchestrator.planner import DOCUMENT_TYPE_SECTIONS
from mainframe_doc_orchestrator.services.previewer import (
    render_dashboard_html,
    render_preview_html,
)
from mainframe_doc_orchestrator.services.workflow_engine import DocumentWorkflowEngine

router = APIRouter(prefix="/documents", tags=["documents"])


def _to_domain_request(payload: DocumentCreateRequest) -> DocumentRequest:
    top_k_chunks, top_k_paths = COMPLEXITY_RETRIEVAL_PARAMS[payload.complexity]

    return DocumentRequest(
        system_id=payload.system_id,
        document_type=payload.document_type,
        output_format="markdown",
        topic=payload.topic,
        section_order=DOCUMENT_TYPE_SECTIONS[payload.document_type],
        retrieval_request=None,  # populated per-section during generate_section
        metadata={
            "filters": payload.model_dump().get("filters", {}),
            "top_k_chunks": top_k_chunks,
            "top_k_paths": top_k_paths,
            **payload.metadata,
        },
    )


@router.post("", response_model=DocumentRunResponse)
async def create_document(
    payload: DocumentCreateRequest,
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
) -> DocumentRunResponse:
    domain_request = _to_domain_request(payload)
    run = await workflow.create_document_run(domain_request)
    if not payload.auto_generate:
        return DocumentRunResponse.model_validate(run)
    run, errors = await workflow.generate_all_sections(run["run_id"])
    response = DocumentRunResponse.model_validate(run)
    if errors:
        response.auto_generate_errors = errors
    return response


@router.post("/{run_id}/generate-all", response_model=DocumentRunResponse)
async def generate_all_sections(
    run_id: str,
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
) -> DocumentRunResponse:
    """Generate all pending sections for an existing run in one call.

    Sections already at ``review_ready`` or ``approved`` are skipped.
    On partial failure the response still returns the run (with sections
    generated so far) and surfaces the errors in ``auto_generate_errors``.
    """
    try:
        run, errors = await workflow.generate_all_sections(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = DocumentRunResponse.model_validate(run)
    if errors:
        response.auto_generate_errors = errors
    return response


@router.post("/{run_id}/generate", response_model=SectionResponse)
async def generate_section(
    run_id: str,
    payload: GenerateRequest,
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
) -> SectionResponse:
    try:
        return SectionResponse.model_validate(
            await workflow.generate_section(run_id, payload.section_name)
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{run_id}/sections/{section_name}/regenerate", response_model=SectionResponse
)
async def regenerate_section(
    run_id: str,
    section_name: str,
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
) -> SectionResponse:
    try:
        return SectionResponse.model_validate(
            await workflow.regenerate_section(run_id, section_name)
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{run_id}/sections/{section_name}/approve", response_model=SectionResponse
)
async def approve_section(
    run_id: str,
    section_name: str,
    payload: ApproveSectionRequest,
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
) -> SectionResponse:
    try:
        return SectionResponse.model_validate(
            await workflow.approve_section(run_id, section_name, payload.notes)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{run_id}/export", response_model=ExportResponse)
async def export_document(
    run_id: str,
    payload: ExportRequest,
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
) -> ExportResponse:
    try:
        result = await workflow.export_document(
            run_id, output_format=payload.output_format
        )
        return ExportResponse.model_validate(result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[DocumentRunResponse], include_in_schema=False)
async def list_documents(
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
    limit: int = 50,
) -> list[DocumentRunResponse]:
    return [
        DocumentRunResponse.model_validate(run)
        for run in await workflow.list_runs(limit=limit)
    ]


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def runs_dashboard(
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
    limit: int = 50,
) -> HTMLResponse:
    """HTML dashboard — open in a browser, not via Swagger."""
    runs = await workflow.list_runs(limit=limit)
    return HTMLResponse(content=render_dashboard_html(runs, limit=limit))


@router.get("/{run_id}", response_model=DocumentRunResponse, include_in_schema=False)
async def get_document(
    run_id: str,
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
) -> DocumentRunResponse:
    try:
        return DocumentRunResponse.model_validate(await workflow.get_run(run_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/{run_id}/sections", response_model=list[SectionResponse], include_in_schema=False
)
async def list_sections(
    run_id: str,
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
) -> list[SectionResponse]:
    try:
        return [
            SectionResponse.model_validate(item)
            for item in await workflow.list_sections(run_id)
        ]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/{run_id}/sections/{section_name}",
    response_model=SectionResponse,
    include_in_schema=False,
)
async def get_section(
    run_id: str,
    section_name: str,
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
) -> SectionResponse:
    try:
        return SectionResponse.model_validate(
            await workflow.get_section(run_id, section_name)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}/preview", response_class=HTMLResponse, include_in_schema=False)
async def preview_document(
    run_id: str,
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
) -> HTMLResponse:
    """Section preview — open in a browser via the dashboard, not via Swagger."""
    try:
        run = await workflow.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HTMLResponse(content=render_preview_html(run))


@router.get(
    "/{run_id}/retrieval-passes",
    response_model=list[RetrievalPassResponse],
    include_in_schema=False,
)
async def list_retrieval_passes(
    run_id: str,
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
) -> list[RetrievalPassResponse]:
    try:
        passes = await workflow.retrieval_pass_repository.list_passes_for_run(run_id)
        return [RetrievalPassResponse.model_validate(item) for item in passes]
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}/events", include_in_schema=False)
async def get_events(
    run_id: str,
    workflow: Annotated[DocumentWorkflowEngine, Depends(get_workflow)],
):
    try:
        return await workflow.get_events(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
