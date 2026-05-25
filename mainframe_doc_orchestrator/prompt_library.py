from __future__ import annotations
from typing import Any

PROMPTS = {
    "executive_summary": {
        "system": "You are a senior mainframe systems analyst writing concise system documentation.",
        "user": """Write the Executive Summary for the system appreciation document. Use only the evidence pack provided. State the system purpose, major batch flows, and the main business capabilities. Avoid unsupported claims. System: {{system_id}} Section: {{section_name}} Question: {{question}} User role: {{user_role}} Prior passes: {{prior_pass_count}} Evidence overview: {{answer_summary}} Supporting chunks: {{supporting_chunks}} Graph paths: {{graph_paths}} Supporting data: {{supporting_data}} Return markdown.""",
    },
    "system_scope": {
        "system": "You are documenting the scope of a legacy mainframe application estate.",
        "user": """Describe the system scope. Enumerate the job streams, programs, copybooks, PARM members, and datasets that appear in the evidence. Mention any boundaries that are implied by the graph and any gaps that remain. System: {{system_id}} Section: {{section_name}} Question: {{question}} Evidence overview: {{answer_summary}} Supporting chunks: {{supporting_chunks}} Graph paths: {{graph_paths}}""",
    },
    "application_landscape": {
        "system": "You are documenting the application landscape and component inventory.",
        "user": """Create an application landscape section listing jobs, steps, procs, programs, copybooks, parm members, and datasets. Group by flow and clearly note relationships. System: {{system_id}} Evidence overview: {{answer_summary}} Supporting chunks: {{supporting_chunks}} Graph paths: {{graph_paths}}""",
    },
    "batch_flow_overview": {
        "system": "You are documenting batch execution flow from JCL, PROC, and COBOL evidence. Use only the chunk_contents and graph_paths provided.",
        "user": """Write the batch flow overview in execution order. Start at the JCL job, expand any PROCs, then explain the invoked programs and the main datasets. Show any conditional or recovery paths separately.

Chunk contents (authoritative source text):
{{chunk_contents}}

Supporting chunk IDs: {{supporting_chunks}}
Graph paths: {{graph_paths}}""",
    },
    "program_inventory": {
        "system": "You are documenting mainframe program inventory. Base all descriptions strictly on the chunk_contents provided. Label any inference clearly as [INFERRED].",
        "user": """Create a program inventory section. For each program, summarize purpose, primary inputs, outputs, copybooks used, and any visible business rules. If program names are opaque, infer purpose carefully and label inferred statements as [INFERRED].

Chunk contents (authoritative source text):
{{chunk_contents}}

Supporting chunk IDs: {{supporting_chunks}}
Graph paths: {{graph_paths}}
Supporting data: {{supporting_data}}""",
    },
    "copybook_and_data_structures": {
        "system": "You are documenting COBOL copybooks and data structures. You must only describe fields that are explicitly present in the chunk_contents provided. Do not infer, invent, or add fields from general COBOL knowledge. If a field is not in the evidence, do not mention it.",
        "user": """Summarize the copybooks and data structures. Translate record layouts into business language where possible. Call out important flags, amounts, identifiers, and status indicators.

CRITICAL: Only list fields that appear verbatim in the chunk_contents below. Do not add any field that is not in the evidence.

Chunk contents (raw source text — use these as the authoritative field list):
{{chunk_contents}}

Supporting chunk IDs: {{supporting_chunks}}
Supporting data: {{supporting_data}}""",
    },
    "business_rules": {
        "system": "You are extracting business rules from COBOL and JCL evidence.",
        "user": """Extract business rules from the evidence pack. Present the rules as bullet points and link each rule to its supporting chunk or graph path. Mark inferred rules clearly. Supporting chunks: {{supporting_chunks}} Evidence items: {{evidence_items}}""",
    },
    "operational_behavior": {
        "system": "You are documenting operational behavior for a batch system.",
        "user": """Describe operational behavior, including scheduling hints, restart paths, error handling, checkpoints, audit logic, and parameter-driven behavior. Supporting chunks: {{supporting_chunks}} Graph paths: {{graph_paths}}""",
    },
    "dependencies_and_integrations": {
        "system": "You are documenting dependencies and integrations.",
        "user": """List dependencies and integrations implied by the evidence pack. Focus on external datasets, utilities, subsystems, and program-to-program calls. Supporting chunks: {{supporting_chunks}} Graph paths: {{graph_paths}} Supporting data: {{supporting_data}}""",
    },
    "gaps_and_assumptions": {
        "system": "You are documenting uncertainty rigorously.",
        "user": """List gaps, assumptions, low-confidence statements, and follow-up questions for SMEs. Do not invent missing facts. Evidence items: {{evidence_items}} Confidence: {{confidence}}""",
    },
}
DEFAULT_SECTION_ORDER = [
    "executive_summary",
    "system_scope",
    "application_landscape",
    "batch_flow_overview",
    "program_inventory",
    "copybook_and_data_structures",
    "business_rules",
    "operational_behavior",
    "dependencies_and_integrations",
    "gaps_and_assumptions",
]
SECTION_TITLES = {
    k: v
    for k, v in [
        ("executive_summary", "Executive Summary"),
        ("system_scope", "System Scope"),
        ("application_landscape", "Application Landscape"),
        ("batch_flow_overview", "Batch Flow Overview"),
        ("program_inventory", "Program Inventory"),
        ("copybook_and_data_structures", "Copybooks and Data Structures"),
        ("business_rules", "Business Rules"),
        ("operational_behavior", "Operational Behavior"),
        ("dependencies_and_integrations", "Dependencies and Integrations"),
        ("gaps_and_assumptions", "Gaps and Assumptions"),
    ]
}


def render_template(text: str, context: dict[str, Any]) -> str:
    rendered = text
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", _stringify(value))
    return rendered


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value, indent=2, sort_keys=True)
    return str(value)
