from __future__ import annotations
from dataclasses import dataclass
from uuid import uuid4
from mainframe_doc_orchestrator.models import (
    DocumentPlan,
    DocumentRequest,
    DocumentSection,
    EvidencePack,
)
from mainframe_doc_orchestrator.prompt_library import (
    DEFAULT_SECTION_ORDER,
    SECTION_TITLES,
)


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


DEFAULT_BLUEPRINTS = {
    "executive_summary": SectionBlueprint(
        "executive_summary",
        SECTION_TITLES["executive_summary"],
        "Summarize the system at a business level.",
        "executive_summary",
        ["topology", "business_rule", "program_summary"],
        "Use the highest-level paths plus the strongest cross-program evidence.",
        min_chunks=3,
        min_paths=2,
        max_tokens=2000,
    ),
    "system_scope": SectionBlueprint(
        "system_scope",
        SECTION_TITLES["system_scope"],
        "Define what is in scope for the system.",
        "system_scope",
        ["jcl", "proc", "program", "copybook"],
        "Collect inventory and boundary evidence.",
        min_chunks=4,
        min_paths=2,
        max_tokens=3000,
    ),
    "application_landscape": SectionBlueprint(
        "application_landscape",
        SECTION_TITLES["application_landscape"],
        "Inventory the application landscape.",
        "application_landscape",
        ["job", "step", "proc", "program", "copybook", "parm"],
        "Collect all visible nodes and relationships.",
        min_chunks=6,
        min_paths=3,
        max_tokens=4000,
    ),
    "batch_flow_overview": SectionBlueprint(
        "batch_flow_overview",
        SECTION_TITLES["batch_flow_overview"],
        "Explain the execution flow and conditional branches.",
        "batch_flow_overview",
        ["job", "step", "proc", "dataset", "program"],
        "Follow the graph in execution order.",
        min_chunks=5,
        min_paths=3,
        max_tokens=4000,
    ),
    "program_inventory": SectionBlueprint(
        "program_inventory",
        SECTION_TITLES["program_inventory"],
        "Document each program and its inputs/outputs.",
        "program_inventory",
        ["program", "copybook", "dataset", "call"],
        "Retrieve each program plus its direct neighborhood.",
        min_chunks=6,
        min_paths=3,
        max_tokens=4000,
    ),
    "copybook_and_data_structures": SectionBlueprint(
        "copybook_and_data_structures",
        SECTION_TITLES["copybook_and_data_structures"],
        "Describe the data structures and record layouts.",
        "copybook_and_data_structures",
        ["copybook", "field", "record", "status", "amount"],
        "Focus on copybook chunks and any paragraphs that consume them.",
        min_chunks=4,
        min_paths=1,
        max_tokens=3500,
    ),
    "business_rules": SectionBlueprint(
        "business_rules",
        SECTION_TITLES["business_rules"],
        "Extract explicit and inferred business rules.",
        "business_rules",
        ["rule", "paragraph", "condition", "evaluate", "if"],
        "Pull code paragraphs that contain conditional or computation logic.",
        min_chunks=4,
        min_paths=1,
        max_tokens=3500,
    ),
    "operational_behavior": SectionBlueprint(
        "operational_behavior",
        SECTION_TITLES["operational_behavior"],
        "Summarize restart, audit, and operational behavior.",
        "operational_behavior",
        ["parm", "checkpoint", "restart", "audit", "error"],
        "Use parameter members and control-flow paragraphs.",
        min_chunks=3,
        min_paths=2,
        max_tokens=2500,
    ),
    "dependencies_and_integrations": SectionBlueprint(
        "dependencies_and_integrations",
        SECTION_TITLES["dependencies_and_integrations"],
        "List system dependencies and integration points.",
        "dependencies_and_integrations",
        ["dataset", "call", "utility", "external"],
        "Traverse outward from programs to neighbors and external nodes.",
        min_chunks=4,
        min_paths=2,
        max_tokens=2500,
    ),
    "gaps_and_assumptions": SectionBlueprint(
        "gaps_and_assumptions",
        SECTION_TITLES["gaps_and_assumptions"],
        "Report uncertainties and missing evidence.",
        "gaps_and_assumptions",
        ["confidence", "unsupported", "inferred"],
        "Pull low-confidence items and unresolved references.",
        min_chunks=2,
        min_paths=0,
        max_tokens=1500,
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
                    f"{plan_id}:{section_name}",
                    blueprint.section_name,
                    blueprint.title,
                    blueprint.objective,
                    blueprint.prompt_key,
                    list(blueprint.required_evidence),
                    blueprint.retrieval_hint,
                    blueprint.min_chunks,
                    blueprint.min_paths,
                    blueprint.max_tokens,
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
