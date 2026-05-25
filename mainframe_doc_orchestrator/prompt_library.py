from __future__ import annotations
from typing import Any

# ---------------------------------------------------------------------------
# Prompt bundles — one entry per section_name.
#
# Each bundle has:
#   "system" — establishes the writer persona and hard grounding constraints.
#   "user"   — template rendered by PromptEngine; uses {{variable}} placeholders.
#
# Phase 1 sections (jcl_and_procs, cobol_programs, copybooks_and_data_structures,
#   operational_behavior, dependencies_and_integrations, gaps_and_assumptions)
#   are grounded in {{chunk_contents}} (raw source text).
#
# Phase 2 sections (application_overview, executive_summary) are synthesis
#   sections that consume {{prior_section_drafts}} instead of raw chunks.
# ---------------------------------------------------------------------------

PROMPTS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------
    # Phase 1 — leaf sections
    # ------------------------------------------------------------------
    "jcl_and_procs": {
        "system": (
            "You are a senior mainframe batch analyst documenting JCL jobs and "
            "procedures. Use only the chunk_contents and graph_paths provided. "
            "Do not describe the internal business logic of COBOL programs — "
            "name the programs and their invoking steps only. "
            "Label any inferences as [INFERRED]."
        ),
        "user": """\
Document all JCL jobs and procedures found in the evidence.

For each **Job** (asset_type JCL):
- State its business purpose (infer from name/comments if necessary — mark [INFERRED]).
- List each **step** in execution order: step name, what it EXECs (PGM or PROC).
- From the graph EXECUTES_PROGRAM edges: name the COBOL program invoked per step.
- From the graph READS_DATASET / WRITES_DATASET edges: list datasets read and written per step.
- Note any COND codes or conditional step logic visible in the source text.

For each **Procedure** (asset_type PROC):
- State its role.
- List proc steps and the programs they execute (EXECUTES_PROGRAM edges).
- Note any dataset DD statements (READS_DATASET / WRITES_DATASET edges).

CRITICAL: Base all field values strictly on chunk_contents below. \
Do NOT describe program logic — only note which program is called.

Chunk contents (authoritative source text):
{{chunk_contents}}

Graph paths (use for EXECUTES_PROGRAM, READS_DATASET, WRITES_DATASET, \
USES_PROC relationships):
{{graph_paths}}

Supporting chunk IDs: {{supporting_chunks}}
System: {{system_id}}
""",
    },
    "cobol_programs": {
        "system": (
            "You are a senior COBOL analyst documenting mainframe programs. "
            "Use only the chunk_contents and graph_paths provided. "
            "Describe business logic visible in the paragraph source text only. "
            "Label inferences as [INFERRED]. "
            "Do NOT reproduce copybook field layouts — reference the copybook name only."
        ),
        "user": """\
Document each COBOL program found in the evidence.

For each **Program**:
1. **Purpose** — state the business function (from paragraph names and logic).
2. **Paragraphs** — for each paragraph chunk, summarise the logic: conditions \
(IF/EVALUATE), computations (COMPUTE/ADD/SUBTRACT), and any business rules visible \
in the source. Quote the paragraph name.
3. **Copybooks used** — from graph USES_COPYBOOK edges: list copybook names only. \
Do not repeat their field layouts here.
4. **Invoked by** — from incoming EXECUTES_PROGRAM graph edges: list the JCL job \
step(s) or PROC step(s) that execute this program.
5. **Datasets** — from READS_DATASET / WRITES_DATASET edges: list datasets read \
and written.

CRITICAL: Only describe logic present verbatim in chunk_contents. \
Do not invent rules. Label inferences [INFERRED].

Chunk contents (authoritative COBOL paragraph source text):
{{chunk_contents}}

Graph paths (use for USES_COPYBOOK, EXECUTES_PROGRAM, READS_DATASET, \
WRITES_DATASET relationships):
{{graph_paths}}

Supporting chunk IDs: {{supporting_chunks}}
System: {{system_id}}
""",
    },
    "copybooks_and_data_structures": {
        "system": (
            "You are documenting COBOL copybooks and data structures. "
            "You must only describe fields that are explicitly present in the "
            "chunk_contents provided. Do not infer, invent, or add fields from "
            "general COBOL knowledge. If a field is not in the evidence, do not "
            "mention it."
        ),
        "user": """\
Document each copybook found in the evidence.

For each **Copybook**:
1. **Fields** — list every field exactly as it appears in the source, translating \
the PIC clause to business language where possible \
(e.g. PIC X(10) → 10-character text; PIC S9(7)V99 COMP-3 → signed packed-decimal \
amount with 2 decimal places). Include level number, field name, and translated type.
2. **Business meaning** — call out fields that are flags, amounts, identifiers, \
or status indicators and explain what each value means if visible from the evidence.
3. **Used by programs** — from incoming USES_COPYBOOK graph edges: list the COBOL \
programs that COPY this copybook.

CRITICAL: Only list fields that appear verbatim in the chunk_contents below. \
Do not add any field that is not in the evidence.

Chunk contents (raw copybook source text — authoritative field list):
{{chunk_contents}}

Graph paths (use for incoming USES_COPYBOOK edges to find consuming programs):
{{graph_paths}}

Supporting chunk IDs: {{supporting_chunks}}
System: {{system_id}}
""",
    },
    "operational_behavior": {
        "system": (
            "You are documenting the operational behavior of a mainframe batch system. "
            "Use only the chunk_contents and graph_paths provided. "
            "Label inferences as [INFERRED]."
        ),
        "user": """\
Describe the operational and run-time behavior of the system.

Cover the following where evidence exists:
- **COND code logic** — which steps are skipped or abended based on prior step return codes.
- **PARM-driven behavior** — what runtime parameters control execution, and what values are used.
- **Restart and recovery** — any visible checkpoint, restart, or abend recovery logic.
- **Error handling** — error counters, suspense queues, or error-file writes.
- **Audit and reporting** — any audit trail writes or report generation steps.

CRITICAL: Base all statements on chunk_contents below.

Chunk contents (JCL, PROC, PARM source text):
{{chunk_contents}}

Graph paths:
{{graph_paths}}

Supporting chunk IDs: {{supporting_chunks}}
System: {{system_id}}
""",
    },
    "dependencies_and_integrations": {
        "system": (
            "You are documenting system dependencies and integration points. "
            "Use only the chunk_contents and graph_paths provided."
        ),
        "user": """\
List all dependencies and integration points implied by the evidence.

Group by type:
- **External datasets** — shared or catalogued datasets read or written (DSN names from DD statements).
- **Utilities** — IBM or third-party utilities invoked (IEBGENER, IDCAMS, IKJEFT01, SORT, etc.).
- **Program-to-program calls** — CALL statements linking programs (CALLS_PROGRAM edges).
- **Subsystem interfaces** — any DB2, CICS, MQ, or other subsystem references visible in the source.

CRITICAL: Only list items present in chunk_contents or graph_paths.

Chunk contents:
{{chunk_contents}}

Graph paths:
{{graph_paths}}

Supporting data:
{{supporting_data}}

Supporting chunk IDs: {{supporting_chunks}}
System: {{system_id}}
""",
    },
    "gaps_and_assumptions": {
        "system": (
            "You are rigorously documenting uncertainty in a mainframe analysis. "
            "Do not invent missing facts."
        ),
        "user": """\
List all gaps, assumptions, low-confidence items, and SME follow-up questions.

For each gap:
- State what is missing or unresolved.
- Identify which chunk or path reference is incomplete.
- Suggest the SME action needed to resolve it.

Mark any statement that is assumed rather than evidenced.

Evidence items (includes structural_required and inferred flags):
{{evidence_items}}

Overall confidence score: {{confidence}}

Supporting chunk IDs: {{supporting_chunks}}
System: {{system_id}}
""",
    },
    # ------------------------------------------------------------------
    # Phase 2 — synthesis sections (consume prior_section_drafts)
    # ------------------------------------------------------------------
    "application_overview": {
        "system": (
            "You are writing an Application Overview section for a mainframe system "
            "appreciation document. "
            "Synthesise only from the verified section drafts provided in "
            "prior_section_drafts. Do not add facts not present in those drafts. "
            "Label any inference as [INFERRED]."
        ),
        "user": """\
Write an Application Overview section that gives a reader a complete inventory and \
component map of the system.

Include:
1. **Component inventory** — table or grouped list of: JCL jobs, PROCs, COBOL programs, \
copybooks, and key datasets. Count each type.
2. **Component relationships** — how jobs invoke PROCs and programs; which programs \
use which copybooks; key dataset flows between components.
3. **Scope boundaries** — what is definitively in scope, what appears to be external, \
and what is unresolved.

Base this section entirely on the verified drafts below. Do not retrieve new evidence.

Prior verified section drafts:
{{prior_section_drafts}}

System: {{system_id}}
""",
    },
    "executive_summary": {
        "system": (
            "You are writing a concise Executive Summary for a mainframe system "
            "appreciation document. "
            "Use only the verified section drafts provided in prior_section_drafts. "
            "Be brief — aim for under 400 words. Do not add facts not in the drafts."
        ),
        "user": """\
Write a concise Executive Summary.

Cover:
1. **System purpose** — what business problem this mainframe estate solves (1–2 sentences).
2. **Major batch flows** — name the key job streams and what each does at a business level.
3. **Key business capabilities** — the most important functions delivered (billing, \
payment processing, reconciliation, etc.).
4. **Component count** — a one-line inventory: X jobs, Y programs, Z copybooks.
5. **Notable risks or gaps** — one sentence summarising the most significant uncertainty.

Base this summary entirely on the verified drafts below.

Prior verified section drafts:
{{prior_section_drafts}}

System: {{system_id}}
""",
    },
    # ------------------------------------------------------------------
    # Additional Phase 1 sections
    # ------------------------------------------------------------------
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
}

# ---------------------------------------------------------------------------
# Section metadata — single source of truth for titles and generation order.
# Kept here so prompt_library remains self-contained for the prompt layer.
# planner.py defines its own DEFAULT_SECTION_ORDER (same list) to avoid a
# circular import with models.py.
# ---------------------------------------------------------------------------

SECTION_TITLES: dict[str, str] = {
    "jcl_and_procs": "JCL Jobs and Procedures",
    "cobol_programs": "COBOL Programs",
    "copybooks_and_data_structures": "Copybooks and Data Structures",
    "operational_behavior": "Operational Behavior",
    "dependencies_and_integrations": "Dependencies and Integrations",
    "gaps_and_assumptions": "Gaps and Assumptions",
    "application_overview": "Application Overview",
    "executive_summary": "Executive Summary",
}

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

# ASSEMBLY_ORDER controls the section sequence in the final exported document.
# It differs from DEFAULT_SECTION_ORDER (which reflects generation/dependency order):
# synthesis sections (executive_summary, application_overview) are generated last
# but should appear first in the reader-facing document.
ASSEMBLY_ORDER: list[str] = [
    "executive_summary",
    "application_overview",
    "jcl_and_procs",
    "cobol_programs",
    "copybooks_and_data_structures",
    "operational_behavior",
    "dependencies_and_integrations",
    "gaps_and_assumptions",
]


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
