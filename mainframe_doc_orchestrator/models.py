from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict
from uuid import uuid4

@dataclass(slots=True)
class RetrievalFilters:
    asset_types: list[str] = field(default_factory=list)
    asset_ids: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)

@dataclass(slots=True)
class RetrievalRequest:
    query: str
    section_name: str
    system_id: str
    top_k_chunks: int = 8
    top_k_paths: int = 15
    filters: RetrievalFilters = field(default_factory=RetrievalFilters)

@dataclass(slots=True)
class GraphPathNode:
    node_id: str
    node_type: str
    properties: Dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class GraphPathEdge:
    source_id: str
    target_id: str
    edge_type: str
    properties: Dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class GraphPath:
    path_id: str
    path_label: str
    nodes: list[GraphPathNode]
    edges: list[GraphPathEdge]
    supporting_chunks: list[str] = field(default_factory=list)

@dataclass(slots=True)
class ChunkContent:
    """Full source text and location for a single chunk, keyed by chunk_id."""
    chunk_id: str
    asset_id: str
    asset_type: str
    chunk_kind: str
    chunk_name: str
    text: str
    source_file: str
    line_start: int
    line_end: int
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class EvidenceItem:
    item_type: str  # "chunk" | "graph_path" | "supporting_data"
    ref: str
    relevance: str

@dataclass(slots=True)
class EvidencePack:
    evidence_request_id: str
    question: str
    section_name: str
    system_id: str
    supporting_chunks: list[str]
    chunk_contents: Dict[str, ChunkContent]
    graph_paths: list[GraphPath]
    supporting_data: Dict[str, Any]
    confidence: float
    evidence_items: list[EvidenceItem] = field(default_factory=list)

@dataclass(slots=True)
class DocumentSection:
    """Section plan + execution state.
    
    Contains both immutable plan fields (section_id, title, objective, etc.)
    and mutable runtime fields (status, draft_markdown, confidence, etc.).
    """
    # ========== Plan fields (immutable after creation) ==========
    section_id: str
    section_name: str
    title: str
    objective: str
    prompt_key: str
    required_evidence: list[str] = field(default_factory=list)
    retrieval_hint: str = ""
    min_chunks: int = 1
    min_paths: int = 0
    max_tokens: int = 0  # 0 = use global draft_writer_max_tokens
    # Asset types forwarded to RetrievalFilters.asset_types.
    # Empty list = no filter (retrieve across all types).
    asset_type_filter: list[str] = field(default_factory=list)
    # Section names that must be review_ready/approved before this section
    # can be generated.  Used for synthesis sections and cascade sections.
    depends_on: list[str] = field(default_factory=list)
    # jcl_analysis cascading: harvest asset IDs from these upstream sections
    # to scope this section's retrieval via RetrievalFilters.asset_ids.
    cascade_from: list[str] = field(default_factory=list)
    # Node types to extract from this section's evidence pack graph paths
    # and store as discovered_asset_ids for downstream cascade sections.
    cascade_node_types: list[str] = field(default_factory=list)
    
    # ========== Runtime fields (populated during execution) ==========
    status: str = "pending"  # pending | in_progress | review_ready | approved
    draft_markdown: str = ""
    evidence_request_id: str | None = None
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)
    retrieval_pass_id: str | None = None
    retrieval_pass_number: int | None = None
    discovered_asset_ids: dict[str, list[str]] = field(default_factory=dict)
    evidence_overview: str = ""
    updated_at: str = ""
    approval_notes: list[str] = field(default_factory=list)

@dataclass(slots=True)
class SectionDraft:
    section_id: str
    section_name: str
    title: str
    content_markdown: str
    evidence_request_id: str
    confidence: float
    notes: list[str] = field(default_factory=list)

@dataclass(slots=True)
class DocumentPlan:
    plan_id: str
    system_id: str
    run_id: str
    sections: list[DocumentSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class DocumentRequest:
    run_id: str = field(default_factory=lambda: str(uuid4()))
    system_id: str = ""
    document_type: str = "system_appreciation"
    output_format: str = "markdown"
    topic: str = ""
    section_order: list[str] = field(default_factory=list)
    prior_run_ids: list[str] = field(default_factory=list)
    retrieval_request: RetrievalRequest | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class DocumentDraft:
    run_id: str
    system_id: str
    title: str
    sections: list[SectionDraft] = field(default_factory=list)
    rendered_markdown: str = ""
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
