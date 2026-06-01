from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from mainframe_doc_orchestrator.models import (
    DocumentPlan,
    DocumentRequest,
    DocumentSection,
)

# Phase 1 sections in generation order, Phase 2 synthesis sections last.
DEFAULT_SECTION_ORDER: list[str] = [
    "jcl_and_procs",  # Phase 1
    "cobol_programs",  # Phase 1
    "copybooks_and_data_structures",  # Phase 1
    "operational_behavior",  # Phase 1
    "dependencies_and_integrations",  # Phase 1
    "gaps_and_assumptions",  # Phase 1
    "application_overview",  # Phase 2 synthesis
    "executive_summary",  # Phase 2 synthesis
]

# Registry: document_type → ordered list of section names to generate.
# This is the single source of truth that drives section planning.
DOCUMENT_TYPE_SECTIONS: dict[str, list[str]] = {
    "system_appreciation": list(DEFAULT_SECTION_ORDER),
    "jcl_analysis": [
        "jcl_analysis_jcl",  # Phase 1 — seed: retrieves JCL chunks
        "jcl_analysis_procs",  # Phase 1 — cascaded from JCL
        "jcl_analysis_cobol",  # Phase 1 — cascaded from JCL + PROCs
        "jcl_analysis_copybooks",  # Phase 1 — cascaded from COBOL
        "jcl_analysis_operational_behavior",  # Phase 1 — cross-cutting: JCL/PROC/PARM
        "jcl_analysis_dependencies_and_integrations",  # Phase 1 — cross-cutting: full lineage
        "jcl_analysis_gaps_and_assumptions",  # Phase 1 — evidence gaps
        "jcl_analysis_application_overview",  # Phase 2 — synthesis
        "jcl_analysis_executive_summary",  # Phase 2 — synthesis
    ],
}

# Human-readable labels used to derive document_title automatically.
DOCUMENT_TYPE_LABELS: dict[str, str] = {
    "system_appreciation": "System Appreciation",
    "jcl_analysis": "JCL Analysis",
}


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
    asset_type_filter: list[str] = field(default_factory=list)
    # Section names that must be review_ready/approved first.
    depends_on: list[str] = field(default_factory=list)
    # jcl_analysis cascading: harvest asset IDs from these upstream sections.
    cascade_from: list[str] = field(default_factory=list)
    # Node types to extract from this section's graph paths for downstream sections.
    cascade_node_types: list[str] = field(default_factory=list)


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
            "Use HAS_STEP to enumerate JCL steps in order. "
            "Use USES_PROC to identify PROCs called by each JCL step. "
            "Use EXECUTES_PROGRAM to identify programs executed directly by JCL steps. "
            "For PROC-invoked steps, traverse HAS_PROC_STEP and EXECUTES_PROGRAM "
            "to list programs executed inside each PROC. "
            "Use READS_DATASET, WRITES_DATASET and READS_OR_WRITES_DATASET to list JCL dataset I/O, "
            "and use PROC step chunk text for PROC-local DD references. "
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
            "Use READS_DATASET / WRITES_DATASET edges for file I/O and CALLS_PROGRAM "
            "for inter-program dependencies. "
            "To identify invokers, trace inbound EXECUTES_PROGRAM edges; when a program is "
            "invoked through a PROC, follow PROC_STEP <- HAS_PROC_STEP <- PROC <- USES_PROC <- STEP. "
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
            "Describe record fields from COPYBOOK chunk text/metadata only; "
            "do not infer fields from COBOL paragraphs."
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
            "Extract COND/restart behavior from JCL EXEC bodies and step chunk text, "
            "and use PROC step chunks for procedure-level control flow. "
            "For PARM assets, use parsed key_values metadata and raw PARM text to document "
            "runtime switches, overrides, and error-handling controls."
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
            "Traverse outward from JCL STEP, PROC_STEP, and COBOL PROGRAM nodes. "
            "Include USES_PROC, EXECUTES_PROGRAM, and CALLS_PROGRAM to map control dependencies. "
            "Use READS_DATASET / WRITES_DATASET / READS_OR_WRITES_DATASET for dataset integration "
            "points, and include utility programs named in EXEC targets."
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
            "Pull low-confidence items and inferred statements from prior section drafts. "
            "Flag unresolved identifiers and partial links seen in parsed evidence "
            "(for example missing EXEC targets, unmapped DD/DSN intent, or ambiguous program/proc names)."
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
        # Depend on ALL Phase 1 sections so every asset type that surfaces in
        # any section (e.g. a control JCL found only via operational_behavior)
        # is visible to the inventory synthesis.
        depends_on=[
            "jcl_and_procs",
            "cobol_programs",
            "copybooks_and_data_structures",
            "operational_behavior",
            "dependencies_and_integrations",
            "gaps_and_assumptions",
        ],
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
    # ------------------------------------------------------------------
    # jcl_analysis document type — cascaded retrieval chain:
    # JCL → (discovers PROCs + COBOLs) → PROCs → (discovers COBOLs) →
    # COBOL → (discovers COPYBOOKs) → COPYBOOKs
    # Each section uses asset IDs harvested from upstream graph paths.
    # ------------------------------------------------------------------
    "jcl_analysis_jcl": SectionBlueprint(
        section_name="jcl_analysis_jcl",
        title="JCL Jobs",
        objective=(
            "Document each JCL job: steps in execution order, programs and PROCs "
            "invoked per step, COND codes, and datasets read or written."
        ),
        prompt_key="jcl_analysis_jcl",
        required_evidence=["job", "step", "dataset"],
        retrieval_hint=(
            "Retrieve JCL chunks for this system. "
            "Use HAS_STEP edges to enumerate step execution order. "
            "Use EXECUTES_PROGRAM for steps that directly run PGM= targets, and USES_PROC "
            "for steps that invoke procedures. "
            "Extract COND/restart behavior from the JCL step text (EXEC body), not inferred logic. "
            "Use READS_DATASET, WRITES_DATASET and READS_OR_WRITES_DATASET edges for dataset I/O. "
            "Do NOT describe COBOL logic — name programs and PROCs only."
        ),
        min_chunks=3,
        min_paths=3,
        max_tokens=3000,
        asset_type_filter=["JCL"],
        cascade_node_types=["PROC", "COBOL", "PROGRAM", "PARM"],
    ),
    "jcl_analysis_procs": SectionBlueprint(
        section_name="jcl_analysis_procs",
        title="Procedures",
        objective=(
            "Document each PROC catalogued by the JCL: steps, programs invoked, "
            "symbolic parameters, and datasets referenced."
        ),
        prompt_key="jcl_analysis_procs",
        required_evidence=["proc", "step", "program", "dataset"],
        retrieval_hint=(
            "Retrieve PROC chunks whose IDs were discovered from the JCL graph. "
            "Use HAS_PROC_STEP to enumerate procedure steps and EXECUTES_PROGRAM "
            "to list programs called by each PROC step. "
            "Use PROC step chunk text to capture symbolic parameters and DD/dataset references "
            "when no dataset edge is present."
        ),
        min_chunks=2,
        min_paths=2,
        max_tokens=3000,
        asset_type_filter=["PROC"],
        depends_on=["jcl_analysis_jcl"],
        cascade_from=["jcl_analysis_jcl"],
        cascade_node_types=["COBOL", "PROGRAM", "PARM"],
    ),
    "jcl_analysis_cobol": SectionBlueprint(
        section_name="jcl_analysis_cobol",
        title="COBOL Programs",
        objective=(
            "Document each COBOL program executed by the JCL or its PROCs: business "
            "logic, paragraphs, copybooks used, datasets accessed, and which JCL "
            "step or PROC invokes it."
        ),
        prompt_key="jcl_analysis_cobol",
        required_evidence=["program", "paragraph", "copybook", "dataset"],
        retrieval_hint=(
            "Retrieve COBOL chunks whose IDs were discovered from JCL and PROC graphs. "
            "Use USES_COPYBOOK edges to list copybooks, READS_DATASET/WRITES_DATASET "
            "for file I/O, and CALLS_PROGRAM for downstream program calls. "
            "Reference invokers by tracing inbound EXECUTES_PROGRAM edges directly from JCL steps "
            "or via PROC_STEP/HAS_PROC_STEP chains."
        ),
        min_chunks=4,
        min_paths=3,
        max_tokens=5000,
        asset_type_filter=["COBOL"],
        depends_on=["jcl_analysis_jcl", "jcl_analysis_procs"],
        cascade_from=["jcl_analysis_jcl", "jcl_analysis_procs"],
        cascade_node_types=["COPYBOOK"],
    ),
    "jcl_analysis_copybooks": SectionBlueprint(
        section_name="jcl_analysis_copybooks",
        title="Copybooks and Data Structures",
        objective=(
            "Document each copybook expanded by the COBOL programs in this JCL lineage: "
            "record layout with PIC clauses in business language, and which programs "
            "expand it."
        ),
        prompt_key="jcl_analysis_copybooks",
        required_evidence=["copybook", "field", "record"],
        retrieval_hint=(
            "Retrieve COPYBOOK chunks whose IDs were discovered from COBOL graphs. "
            "Use incoming USES_COPYBOOK edges to list which COBOL programs expand each "
            "copybook. Describe fields from copybook text/metadata only, preserving "
            "verbatim structure where needed for accuracy."
        ),
        min_chunks=2,
        min_paths=1,
        max_tokens=3500,
        asset_type_filter=["COPYBOOK"],
        depends_on=["jcl_analysis_cobol"],
        cascade_from=["jcl_analysis_cobol"],
    ),
    # ------------------------------------------------------------------
    # jcl_analysis Phase 1 — cross-cutting sections
    # These are generated after the four cascaded sections so that all
    # lineage asset IDs have been discovered and can be used to scope
    # retrieval via cascade_from.
    # ------------------------------------------------------------------
    "jcl_analysis_operational_behavior": SectionBlueprint(
        section_name="jcl_analysis_operational_behavior",
        title="Operational Behavior",
        objective=(
            "Summarise the operational and run-time behavior of this JCL job and its "
            "related PROCs and PARM members: COND/restart logic, PARM-driven switches, "
            "symbolic parameters, error handling, checkpoints, and audit trails."
        ),
        prompt_key="jcl_analysis_operational_behavior",
        required_evidence=["parm", "cond", "restart", "error", "audit"],
        retrieval_hint=(
            "Retrieve JCL, PROC, and PARM chunks whose IDs were discovered from the "
            "jcl_analysis_jcl and jcl_analysis_procs sections. "
            "Extract COND/restart behavior from JCL EXEC bodies and PROC step chunk text. "
            "For PARM assets, use parsed key_values metadata and raw PARM text to document "
            "runtime switches, overrides, and error-handling controls. "
            "Use USES_PARM edges to link PARM members to the steps that consume them."
        ),
        min_chunks=2,
        min_paths=1,
        max_tokens=2500,
        asset_type_filter=["JCL", "PROC", "PARM"],
        depends_on=["jcl_analysis_jcl", "jcl_analysis_procs"],
    ),
    "jcl_analysis_dependencies_and_integrations": SectionBlueprint(
        section_name="jcl_analysis_dependencies_and_integrations",
        title="Dependencies and Integrations",
        objective=(
            "List all external datasets, utilities, subsystems, and program-to-program "
            "call dependencies discovered within this JCL lineage."
        ),
        prompt_key="jcl_analysis_dependencies_and_integrations",
        required_evidence=["dataset", "call", "utility", "external"],
        retrieval_hint=(
            "Retrieve all asset chunks whose IDs were discovered across the full JCL "
            "lineage (JCL, PROC, COBOL, COPYBOOK). "
            "Traverse USES_PROC, EXECUTES_PROGRAM, and CALLS_PROGRAM to map control "
            "dependencies within this lineage. "
            "Use READS_DATASET / WRITES_DATASET / READS_OR_WRITES_DATASET for dataset "
            "integration points, and identify utility programs named in EXEC targets. "
            "Flag any subsystem references (DB2, CICS, MQ, IMS) found in COBOL source "
            "or JCL DD statements."
        ),
        min_chunks=3,
        min_paths=2,
        max_tokens=2500,
        asset_type_filter=[],
        depends_on=[
            "jcl_analysis_jcl",
            "jcl_analysis_procs",
            "jcl_analysis_cobol",
            "jcl_analysis_copybooks",
        ],
        cascade_from=[
            "jcl_analysis_jcl",
            "jcl_analysis_procs",
            "jcl_analysis_cobol",
            "jcl_analysis_copybooks",
        ],
    ),
    "jcl_analysis_gaps_and_assumptions": SectionBlueprint(
        section_name="jcl_analysis_gaps_and_assumptions",
        title="Gaps and Assumptions",
        objective=(
            "Report low-confidence items, unresolved identifiers, inferred facts, "
            "and follow-up questions for SMEs arising from this JCL analysis."
        ),
        prompt_key="jcl_analysis_gaps_and_assumptions",
        required_evidence=["confidence", "unsupported", "inferred"],
        retrieval_hint=(
            "Pull low-confidence items and inferred statements from all prior "
            "jcl_analysis section drafts. "
            "Flag unresolved identifiers and partial links across the full lineage "
            "(missing EXEC targets, unmapped DD/DSN intent, unretrieved COBOL or copybook "
            "sources, ambiguous PARM values, or incomplete COND code context)."
        ),
        min_chunks=1,
        min_paths=0,
        max_tokens=1500,
        asset_type_filter=[],
        depends_on=[
            "jcl_analysis_jcl",
            "jcl_analysis_procs",
            "jcl_analysis_cobol",
            "jcl_analysis_copybooks",
            "jcl_analysis_operational_behavior",
            "jcl_analysis_dependencies_and_integrations",
        ],
        cascade_from=[
            "jcl_analysis_jcl",
            "jcl_analysis_procs",
            "jcl_analysis_cobol",
            "jcl_analysis_copybooks",
            "jcl_analysis_operational_behavior",
            "jcl_analysis_dependencies_and_integrations",
        ],
    ),
    # ------------------------------------------------------------------
    # jcl_analysis Phase 2 — synthesis sections
    # These consume prior draft text exclusively; no fresh chunk retrieval.
    # ------------------------------------------------------------------
    "jcl_analysis_application_overview": SectionBlueprint(
        section_name="jcl_analysis_application_overview",
        title="Application Overview",
        objective=(
            "Synthesise a component inventory and execution lineage for this JCL job "
            "(job, PROCs, COBOL programs, copybooks, datasets, PARM members) with "
            "relationships and scope boundaries, drawn from the verified Phase 1 drafts."
        ),
        prompt_key="jcl_analysis_application_overview",
        required_evidence=[],
        retrieval_hint=(
            "Synthesis section — use prior_section_drafts exclusively. "
            "No fresh chunk retrieval required."
        ),
        min_chunks=0,
        min_paths=0,
        max_tokens=4000,
        asset_type_filter=[],
        depends_on=[
            "jcl_analysis_jcl",
            "jcl_analysis_procs",
            "jcl_analysis_cobol",
            "jcl_analysis_copybooks",
        ],
    ),
    "jcl_analysis_executive_summary": SectionBlueprint(
        section_name="jcl_analysis_executive_summary",
        title="Executive Summary",
        objective=(
            "Write a concise business-level summary of this JCL job: purpose, "
            "batch execution flow, key capabilities, asset counts, and top risk."
        ),
        prompt_key="jcl_analysis_executive_summary",
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
            "jcl_analysis_jcl",
            "jcl_analysis_procs",
            "jcl_analysis_cobol",
            "jcl_analysis_copybooks",
            "jcl_analysis_operational_behavior",
            "jcl_analysis_dependencies_and_integrations",
            "jcl_analysis_gaps_and_assumptions",
        ],
    ),
}


class MainframeDocumentPlanner:
    def __init__(self, section_order: list[str] | None = None) -> None:
        self.section_order = section_order or list(DEFAULT_SECTION_ORDER)

    def plan(self, request: DocumentRequest) -> DocumentPlan:
        plan_id = str(uuid4())
        sections: list[DocumentSection] = []
        active_order = request.section_order or self.section_order
        now_iso = datetime.now(timezone.utc).isoformat()

        # Derive a complexity-aware min_chunks floor from the request's top_k_chunks.
        # Formula: max(3, top_k_chunks // 5) — scales validator sensitivity so that
        # complex estates (top_k=35 → floor=7) flag under-retrieval earlier than
        # simple ones (top_k=10 → floor=3).  The blueprint's own min_chunks acts as
        # a per-section lower bound so tightly-scoped sections (copybooks, gaps) are
        # never penalised against the global floor.
        top_k_chunks: int = int(request.metadata.get("top_k_chunks", 10))
        complexity_min_chunks_floor: int = max(3, top_k_chunks // 5)
        # Scale max_tokens proportionally for evidence sections so the LLM has
        # enough output budget to cover all assets in a complex estate.
        # Formula: max(blueprint, blueprint * top_k / 20) — at top_k=35 this is
        # 1.75x the blueprint value; at top_k=20 it's 1.0x (no change).
        # Synthesis sections (max_tokens capped at their own value) are unchanged.
        complexity_max_tokens_scale: float = max(1.0, top_k_chunks / 20)

        for section_name in active_order:
            blueprint = DEFAULT_BLUEPRINTS[section_name]
            # Apply the complexity floor only to evidence sections (min_chunks > 0).
            # Synthesis sections (min_chunks == 0) are left unchanged.
            effective_min_chunks = (
                max(blueprint.min_chunks, complexity_min_chunks_floor)
                if blueprint.min_chunks > 0
                else 0
            )
            # Scale output budget for evidence sections; synthesis sections keep
            # their fixed cap so the inventory/summary stays concise.
            effective_max_tokens = (
                int(blueprint.max_tokens * complexity_max_tokens_scale)
                if blueprint.min_chunks > 0 and blueprint.max_tokens > 0
                else blueprint.max_tokens
            )
            sections.append(
                DocumentSection(
                    section_id=f"{plan_id}:{section_name}",
                    section_name=blueprint.section_name,
                    title=blueprint.title,
                    objective=blueprint.objective,
                    prompt_key=blueprint.prompt_key,
                    required_evidence=list(blueprint.required_evidence),
                    retrieval_hint=blueprint.retrieval_hint,
                    min_chunks=effective_min_chunks,
                    min_paths=blueprint.min_paths,
                    max_tokens=effective_max_tokens,
                    asset_type_filter=list(blueprint.asset_type_filter),
                    depends_on=list(blueprint.depends_on),
                    cascade_from=list(blueprint.cascade_from),
                    cascade_node_types=list(blueprint.cascade_node_types),
                    # Runtime fields initialized with defaults
                    status="pending",
                    draft_markdown="",
                    evidence_request_id=None,
                    confidence=0.0,
                    notes=[],
                    retrieval_pass_id=None,
                    retrieval_pass_number=None,
                    discovered_asset_ids={},
                    evidence_overview="",
                    updated_at=now_iso,
                    approval_notes=[],
                )
            )
        return DocumentPlan(
            plan_id=plan_id,
            system_id=request.system_id,
            run_id=request.run_id,
            sections=sections,
            metadata={
                "document_type": request.document_type,
                "topic": request.topic,
            },
        )
