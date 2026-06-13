from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# Maps complexity level → (top_k_chunks, top_k_paths).
# top_k_chunks: number of text chunks retrieved per section.
# top_k_paths:  number of graph execution paths retrieved per section.
COMPLEXITY_RETRIEVAL_PARAMS: dict[str, tuple[int, int]] = {
    "simple":  (10, 10),
    "medium":  (20, 20),
    "complex": (35, 35),
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
    document_type: Literal["system_appreciation", "jcl_analysis"] = "system_appreciation"
    topic: str = ""
    complexity: Literal["simple", "medium", "complex"] = Field(
        default="medium",
        description=(
            "Complexity of the assets being analysed. Drives top_k_chunks and top_k_paths "
            "automatically: simple=(10,10), medium=(20,20), complex=(35,35). "
            "Provide asset_ids or asset_types in filters to scope retrieval; both are optional "
            "but at least one is strongly recommended for multi-job estates."
        ),
    )
    filters: RetrievalFiltersModel = Field(default_factory=RetrievalFiltersModel)
    metadata: dict[str, Any] = Field(default_factory=dict)
    auto_generate: bool = Field(
        default=False,
        description="When True, all sections are generated sequentially before returning. "
                    "On partial failure the run is still returned with errors listed in auto_generate_errors.",
    )


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
    auto_generate_errors: list[dict[str, Any]] | None = Field(
        default=None,
        description="Populated only when auto_generate=True and one or more sections "
                    "failed. Each entry contains section_name and error.",
    )


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
    file_path: str | None = None
