from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# Maps caller-supplied JCL complexity hint to a recommended top_k_paths value.
# simple  — 1-2 steps, 1 program each, few copybooks  (~9 leaf paths)
# medium  — 3-5 steps, 1-2 programs, moderate copybooks (~15 leaf paths)
# complex — 5+ steps, multiple programs, many copybooks (~25 leaf paths)
JCL_COMPLEXITY_TOP_K: dict[str, int] = {
    "simple": 9,
    "medium": 15,
    "complex": 25,
}


class RetrievalFiltersModel(BaseModel):
    asset_types: list[str] = Field(default_factory=list)
    asset_ids: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)


class RetrievalRequestModel(BaseModel):
    query: str = ""
    section_name: str = "batch_flow_overview"
    system_id: str = ""
    top_k_chunks: int = 8
    top_k_paths: int = 15
    filters: RetrievalFiltersModel = Field(default_factory=RetrievalFiltersModel)


class DocumentCreateRequest(BaseModel):
    system_id: str
    document_title: str | None = None
    document_type: str = "system_appreciation"
    user_role: str = "analyst"
    topic: str = ""
    scope: str = ""
    section_order: list[str] = Field(default_factory=list)
    top_k_chunks: int = 8
    # Explicit override — takes precedence over jcl_complexity when provided.
    top_k_paths: int | None = None
    # Convenience hint: drives top_k_paths when top_k_paths is not explicitly set.
    # simple=9, medium=15 (default), complex=25
    jcl_complexity: Literal["simple", "medium", "complex"] = "medium"
    filters: RetrievalFiltersModel = Field(default_factory=RetrievalFiltersModel)
    retrieval_request: RetrievalRequestModel | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenerateRequest(BaseModel):
    section_name: str | None = None


class ApproveSectionRequest(BaseModel):
    notes: str | None = None


class ExportRequest(BaseModel):
    output_format: Literal["markdown"] = "markdown"


class SectionResponse(BaseModel):
    section_id: str
    section_name: str
    title: str
    objective: str | None = None
    prompt_key: str | None = None
    status: str | None = None
    draft_markdown: str = ""
    confidence: float = 0.0
    evidence_request_id: str | None = None
    retrieval_pass_id: str | None = None
    retrieval_pass_number: int | None = None
    evidence_overview: str | None = None
    notes: list[str] = Field(default_factory=list)
    approval_notes: list[str] = Field(default_factory=list)
    updated_at: str | None = None


class DocumentRunResponse(BaseModel):
    run_id: str
    document_title: str
    system_id: str
    status: str
    created_at: datetime | str
    completed_at: datetime | str | None = None
    plan: dict[str, Any]
    export_artifact: dict[str, Any] | None = None


class RetrievalPassResponse(BaseModel):
    pass_id: str
    run_id: str
    section_name: str
    pass_number: int
    query: str
    evidence_request_id: str | None = None
    status: str
    created_at: datetime | str


class ExportResponse(BaseModel):
    run_id: str
    format: str
    content: str
