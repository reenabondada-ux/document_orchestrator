from __future__ import annotations
from dataclasses import dataclass, field
from uuid import uuid4
from mainframe_doc_orchestrator.models import (
    DocumentPlan,
    DocumentRequest,
    DocumentSection,
    EvidencePack,
)

# Phase 1 sections in generation order, Phase 2 synthesis sections last.
DEFAULT_SECTION_ORDER: list[str] = [
    "jcl_and_procs",
    "cobol_programs",
    "copybooks_and_data_structures",
    "operational_behavior",
    "dependencies_and_integrations",
    "gaps_and_assumptions",
    "application_overview",
    "executive_summary",
]


@dataclass(slots=True)
class SectionBlueprint:
    section_name: str
    title: str
    objective: str
    prompt_key: str
    required_evidence: list[str]
    retrieval_hint: str
    min_chunks: int = 1
    min_paths: int = 0
    max_tokens: int = 0  # 0 = use global draft_writer_max_tokens
    # Forwarded to RetrievalFilters.asset_types.  Empty = no filter.
    asset_type_filter: list[str] = field(default_factory=list)
    # Section names that must be review_ready/approved first.
    depends_on: list[str] = field(default_factory=list)


DEFAULT_BLUEPRINTS: dict[str, SectionBlueprint] = {
    # ------------------------------------------------------------------
    # Phase 1 — Evidence-grounded leaf sections (each scoped to one or two
    # asset_types so retrieval stays focused and grounded).
    # Generation order: jcl_and_procs → cobol_programs →
    #   copybooks_and_data_structures → operational_behavior →
    #   dependencies_and_integrations → gaps_and_assumptions
    # ------------------------------------------------------------------
    "jcl_and_procs": SectionBlueprint(
        section_name="jcl_and_procs",
        title="JCL Jobs and Procedures",
        objective=(
            "Document every job stream and procedure: steps, execution order, "
            "COND codes, programs invoked, and datasets read or written."
        ),
        prompt_key="jcl_and_procs",
        required_evidence=["job", "step", "proc", "dataset", "program"],
        retrieval_hint=(
            "Retrieve JCL and PROC chunks. "
            "Use EXECUTES_PROGRAM and USES_PROC graph edges to identify programs "
            "executed by each step. "
            "Use READS_DATASET and WRITES_DATASET edges to list datasets. "
            "Do NOT describe COBOL program logic — name programs only."
        ),
        min_chunks=5,
        min_paths=4,
        max_tokens=4000,
        asset_type_filter=["JCL", "PROC"],
    ),
    "cobol_programs": SectionBlueprint(
        section_name="cobol_programs",
        title="COBOL Programs",
        objective=(
            "Document each COBOL program: its business logic, paragraphs, "
            "rules, copybooks used, datasets accessed, and which JCL/PROC invokes it."
        ),
        prompt_key="cobol_programs",
        required_evidence=["program", "paragraph", "copybook", "dataset", "rule"],
        retrieval_hint=(
            "Retrieve COBOL paragraph chunks. "
            "Use USES_COPYBOOK edges to list copybooks consumed by each program. "
            "Use incoming EXECUTES_PROGRAM / USES_PROC edges to identify which "
            "job steps invoke each program. "
            "Use READS_DATASET / WRITES_DATASET edges for file I/O. "
            "Describe business logic from chunk text only — label inferences [INFERRED]. "
            "Do NOT reproduce copybook field layouts here."
        ),
        min_chunks=6,
        min_paths=4,
        max_tokens=5000,
        asset_type_filter=["COBOL"],
    ),
    "copybooks_and_data_structures": SectionBlueprint(
        section_name="copybooks_and_data_structures",
        title="Copybooks and Data Structures",
        objective=(
            "Document each copybook's record layout with PIC clauses translated "
            "to business language, and list which COBOL programs expand each copybook."
        ),
        prompt_key="copybooks_and_data_structures",
        required_evidence=["copybook", "field", "record", "status", "amount"],
        retrieval_hint=(
            "Retrieve COPYBOOK chunks only. "
            "Use incoming USES_COPYBOOK graph edges to find which COBOL programs "
            "COPY each copybook — list these programs under each copybook entry. "
            "Only describe fields present verbatim in the chunk text."
        ),
        min_chunks=3,
        min_paths=2,
        max_tokens=3500,
        asset_type_filter=["COPYBOOK"],
    ),
    "operational_behavior": SectionBlueprint(
        section_name="operational_behavior",
        title="Operational Behavior",
        objective=(
            "Summarise scheduling hints, COND restart logic, PARM-driven behavior, "
            "error handling, checkpoints, and audit trails."
        ),
        prompt_key="operational_behavior",
        required_evidence=["parm", "checkpoint", "restart", "audit", "error", "cond"],
        retrieval_hint=(
            "Retrieve JCL, PROC, and PARM chunks. "
            "Focus on COND codes, PARM members, conditional step execution, "
            "and any restart or recovery paths visible in the JCL."
        ),
        min_chunks=3,
        min_paths=2,
        max_tokens=2500,
        asset_type_filter=["JCL", "PROC", "PARM"],
    ),
    "dependencies_and_integrations": SectionBlueprint(
        section_name="dependencies_and_integrations",
        title="Dependencies and Integrations",
        objective=(
            "List all external datasets, utilities, subsystems, and "
            "program-to-program call dependencies."
        ),
        prompt_key="dependencies_and_integrations",
        required_evidence=["dataset", "call", "utility", "external"],
        retrieval_hint=(
            "Traverse outward from programs and steps to their dataset and "
            "utility neighbours. Include CALLS_PROGRAM, READS_DATASET, "
            "WRITES_DATASET, and USES_PROC edges."
        ),
        min_chunks=4,
        min_paths=3,
        max_tokens=2500,
        asset_type_filter=[],
    ),
    "gaps_and_assumptions": SectionBlueprint(
        section_name="gaps_and_assumptions",
        title="Gaps and Assumptions",
        objective=(
            "Report low-confidence items, unresolved identifiers, inferred "
            "facts, and follow-up questions for SMEs."
        ),
        prompt_key="gaps_and_assumptions",
        required_evidence=["confidence", "unsupported", "inferred"],
        retrieval_hint=(
            "Pull low-confidence items and evidence_items flagged as "
            "structural_required or inferred."
        ),
        min_chunks=2,
        min_paths=0,
        max_tokens=1500,
        asset_type_filter=[],
    ),
    # ------------------------------------------------------------------
    # Phase 2 — Synthesis sections.
    # These sections consume prior draft text via depends_on; they do
    # minimal or no fresh chunk retrieval.  They must be generated AFTER
    # all Phase 1 sections they depend on are review_ready or approved.
    # ------------------------------------------------------------------
    "application_overview": SectionBlueprint(
        section_name="application_overview",
        title="Application Overview",
        objective=(
            "Synthesise a component inventory (jobs, procs, programs, copybooks, "
            "datasets) with relationships and scope boundaries, drawn from the "
            "verified Phase 1 section drafts."
        ),
        prompt_key="application_overview",
        required_evidence=[],
        retrieval_hint=(
            "Synthesis section — use prior_section_drafts exclusively. "
            "No fresh chunk retrieval required."
        ),
        min_chunks=0,
        min_paths=0,
        max_tokens=4000,
        asset_type_filter=[],
        depends_on=["jcl_and_procs", "cobol_programs", "copybooks_and_data_structures"],
    ),
    "executive_summary": SectionBlueprint(
        section_name="executive_summary",
        title="Executive Summary",
        objective=(
            "Write a concise business-level summary of the system: purpose, "
            "major batch flows, key capabilities, and component counts."
        ),
        prompt_key="executive_summary",
        required_evidence=[],
        retrieval_hint=(
            "Synthesis section — use prior_section_drafts exclusively. "
            "No fresh chunk retrieval required."
        ),
        min_chunks=0,
        min_paths=0,
        max_tokens=2000,
        asset_type_filter=[],
        depends_on=[
            "jcl_and_procs",
            "cobol_programs",
            "copybooks_and_data_structures",
            "operational_behavior",
            "dependencies_and_integrations",
            "gaps_and_assumptions",
        ],
    ),
}


class MainframeDocumentPlanner:
    def __init__(self, section_order: list[str] | None = None) -> None:
        self.section_order = section_order or list(DEFAULT_SECTION_ORDER)

    def plan(
        self, request: DocumentRequest, evidence_pack: EvidencePack | None = None
    ) -> DocumentPlan:
        plan_id = str(uuid4())
        sections: list[DocumentSection] = []
        for section_name in self.section_order:
            blueprint = DEFAULT_BLUEPRINTS[section_name]
            sections.append(
                DocumentSection(
                    section_id=f"{plan_id}:{section_name}",
                    section_name=blueprint.section_name,
                    title=blueprint.title,
                    objective=blueprint.objective,
                    prompt_key=blueprint.prompt_key,
                    required_evidence=list(blueprint.required_evidence),
                    retrieval_hint=blueprint.retrieval_hint,
                    min_chunks=blueprint.min_chunks,
                    min_paths=blueprint.min_paths,
                    max_tokens=blueprint.max_tokens,
                    asset_type_filter=list(blueprint.asset_type_filter),
                    depends_on=list(blueprint.depends_on),
                )
            )
        return DocumentPlan(
            plan_id=plan_id,
            system_id=request.system_id,
            run_id=request.run_id,
            sections=sections,
            metadata={
                "document_style": request.document_style,
                "user_role": request.user_role,
                "topic": request.topic,
                "has_initial_evidence": evidence_pack is not None,
            },
        )
