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
            "Use only the chunk_contents and graph_paths provided. "
            "COBOL PERFORM statements invoke internal paragraphs within the same program "
            "and are NOT inter-program calls. Never list PERFORM targets as program-to-program "
            "dependencies. Only CALL statements evidenced by CALLS_PROGRAM graph edges "
            "represent true program-to-program dependencies."
        ),
        "user": """\
List all dependencies and integration points implied by the evidence.

Group by type:
- **External datasets** — shared or catalogued datasets read or written (DSN names from DD statements).
- **Utilities** — IBM or third-party utilities invoked (IEBGENER, IDCAMS, IKJEFT01, SORT, etc.).
- **Program-to-program calls** — only COBOL CALL statements evidenced by CALLS_PROGRAM graph edges. \
If no CALLS_PROGRAM edge exists for a program, write "None identified" for this group. \
DO NOT list PERFORM statements — PERFORM invokes an internal paragraph within the same program, \
not an external program.
- **Subsystem interfaces** — any DB2, CICS, MQ, or other subsystem references visible in the source.

CRITICAL: Only list items present in chunk_contents or graph_paths. \
A program calling its own paragraph via PERFORM is NOT a dependency.

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
    # jcl_analysis document type — cascaded retrieval sections
    # ------------------------------------------------------------------
    "jcl_analysis_jcl": {
        "system": (
            "You are a senior mainframe batch analyst documenting JCL jobs for a "
            "targeted JCL analysis. Use only the chunk_contents and graph_paths "
            "provided. Do not describe COBOL business logic — name programs and "
            "PROCs only. Label any inference as [INFERRED]."
        ),
        "user": """\
Document all JCL jobs found in the evidence.

For each **Job**:
- State its business purpose (infer from name/comments — mark [INFERRED]).
- List each **step** in execution order: step name and what it EXECs (PGM or PROC).
- From EXECUTES_PROGRAM graph edges: name the COBOL program invoked per step.
- From USES_PROC graph edges: name any catalogued PROC expanded per step.
- From READS_DATASET / WRITES_DATASET edges: list datasets read and written per step.
- Note any COND codes or conditional step logic visible in the source.

CRITICAL: Base all values strictly on chunk_contents. Do not invent logic.

Chunk contents:
{{chunk_contents}}

Graph paths (EXECUTES_PROGRAM, USES_PROC, READS_DATASET, WRITES_DATASET, READS_OR_WRITES_DATASET):
{{graph_paths}}

System: {{system_id}}
""",
    },
    "jcl_analysis_procs": {
        "system": (
            "You are a senior mainframe batch analyst documenting catalogued PROC members "
            "discovered via a JCL analysis. Use only the chunk_contents and graph_paths provided. "
            "Do not describe COBOL business logic — name programs only."
            "Label any inference as [INFERRED]."
        ),
        "user": """\
Document each PROC found in the evidence. These PROCs were discovered from the JCL \
job steps analysed in the previous section.

For each **Procedure**:
- State its role (infer from name/comments — mark [INFERRED]).
- List proc steps in order: step name, PGM invoked.
- From EXECUTES_PROGRAM edges: name the COBOL program executed per step.
- From READS_DATASET / WRITES_DATASET edges: list datasets per step.
- Note any symbolic parameters (PARM or SET statements).
- Reference which JCL job step invokes this PROC (from prior_section_drafts below).

CRITICAL: Only describe content present in chunk_contents. Do not invent logic.

Chunk contents:
{{chunk_contents}}

Graph paths:
{{graph_paths}}

Prior section context (JCL jobs that invoke these PROCs):
{{prior_section_drafts}}

System: {{system_id}}
""",
    },
    "jcl_analysis_cobol": {
        "system": (
            "You are a senior mainframe batch analyst documenting COBOL programs executed "
            "by a specific JCL / PROC lineage. Use only the chunk_contents and graph_paths provided. "
            "Describe business logic visible in paragraph source text only. "
            "Label inferences as [INFERRED]. "
            "Do NOT reproduce copybook field layouts — reference the copybook name only."
        ),
        "user": """\
Document each COBOL program found in the evidence. These programs were discovered \
from the JCL and PROC graphs analysed in prior sections.

For each **Program**:
1. **Purpose** — state the business function from paragraph names and logic.
2. **Paragraphs** — summarise each paragraph: conditions, computations, business rules.
3. **Copybooks used** — from USES_COPYBOOK edges: list copybook names only.
4. **Invoked by** — which JCL step or PROC step executes this program \
(from prior_section_drafts).
5. **Datasets** — from READS_DATASET / WRITES_DATASET edges.

CRITICAL: Only describe logic present verbatim in chunk_contents.

Chunk contents:
{{chunk_contents}}

Graph paths:
{{graph_paths}}

Prior section context (JCL jobs and PROCs that invoke these programs):
{{prior_section_drafts}}

System: {{system_id}}
""",
    },
    "jcl_analysis_copybooks": {
        "system": (
            "You are  a senior mainframe batch analyst documenting COBOL copybooks expanded in "
            "a specific JCL lineage. Only describe fields explicitly present in the chunk_contents. "
            "Do not infer or invent fields."
        ),
        "user": """\
Document each copybook found in the evidence. These copybooks were discovered from \
the COBOL programs analysed in the prior section.

For each **Copybook**:
1. **Fields** — list every field as it appears in the source, translating PIC clauses \
to business language (e.g. PIC X(10) → 10-character text).
2. **Business meaning** — call out flags, amounts, identifiers, and status indicators.
3. **Used by programs** — from incoming USES_COPYBOOK edges: list the COBOL programs \
that COPY this copybook (cross-reference with prior_section_drafts where helpful).

CRITICAL: Only list fields that appear verbatim in chunk_contents.

Chunk contents:
{{chunk_contents}}

Graph paths (incoming USES_COPYBOOK edges):
{{graph_paths}}

Prior section context (COBOL programs that expand these copybooks):
{{prior_section_drafts}}

System: {{system_id}}
""",
    },
    # ------------------------------------------------------------------
    # jcl_analysis Phase 1 — cross-cutting sections (JCL-lineage scoped)
    # ------------------------------------------------------------------
    "jcl_analysis_operational_behavior": {
        "system": (
            "You are documenting the operational and run-time behavior of a specific "
            "mainframe JCL job and its catalogued PROCs and PARM members. "
            "Use only the chunk_contents and graph_paths provided. "
            "All observations must relate solely to the JCL lineage under analysis. "
            "Label any inference as [INFERRED]."
        ),
        "user": """\
Describe the operational and run-time behavior of this JCL job and its related assets.

Cover the following where evidence exists:
- **COND code logic** — which steps are skipped or fail based on prior step return codes \
(source: JCL EXEC COND= and PROC step COND= clauses in chunk_contents).
- **PARM-driven behavior** — what runtime parameters are passed via EXEC PARM= or PARM \
members; what values control execution paths, overrides, or switches.
- **Symbolic parameters** — PROC symbolic parameters (SET / EXEC PROC= overrides) that \
alter step behavior.
- **Restart and recovery** — any checkpoint, restart marker, or abend recovery logic \
visible in JCL or PROC step text.
- **Error handling** — error counters, suspense writes, or error-file DD statements.
- **Audit and reporting** — audit trail writes or report generation steps.

CRITICAL: Base all statements on chunk_contents. Do not describe logic absent from \
the evidence.

Chunk contents (JCL, PROC, PARM source text for this lineage):
{{chunk_contents}}

Graph paths (USES_PARM, READS_DATASET, WRITES_DATASET edges):
{{graph_paths}}

Prior section context (JCL jobs and PROCs in this lineage):
{{prior_section_drafts}}

System: {{system_id}}
""",
    },
    "jcl_analysis_dependencies_and_integrations": {
        "system": (
            "You are documenting the dependencies and integration points of a specific "
            "mainframe JCL job and its entire asset lineage (PROCs, COBOL programs, "
            "copybooks, datasets, PARM members). "
            "Use only the chunk_contents and graph_paths provided. "
            "Scope all observations to the JCL under analysis and its directly or "
            "indirectly related assets. "
            "COBOL PERFORM statements invoke internal paragraphs within the same program "
            "and are NOT inter-program calls. The chunk metadata field "
            "'internal_paragraph_performs' lists paragraph names invoked via PERFORM — "
            "never include these as program-to-program dependencies. Only CALL statements "
            "evidenced by CALLS_PROGRAM graph edges represent true inter-program dependencies."
        ),
        "user": """\
List all dependencies and integration points for this JCL lineage.

Group by type:
- **External datasets** — shared or catalogued datasets read or written by any step \
or program in this lineage (DSN values from DD statements and READS/WRITES edges). \
Note whether each is input-only, output-only, or bidirectional.
- **Utilities** — IBM or third-party utilities invoked by JCL or PROC steps \
(e.g. IEBGENER, IDCAMS, IKJEFT01, SORT, DFSORT). List the invoking step.
- **Program-to-program calls** — only COBOL programs that invoke other COBOL programs \
via a CALL statement, evidenced by a CALLS_PROGRAM graph edge (caller → callee). \
If no CALLS_PROGRAM edge exists, write "None identified" for this group. \
DO NOT list PERFORM statements or names from 'internal_paragraph_performs' metadata — \
PERFORM invokes an internal paragraph within the same program, not an external program.
- **Subsystem interfaces** — any DB2, CICS, MQ, IMS, or other subsystem references \
visible in COBOL source or JCL DD statements within this lineage.
- **PARM dependencies** — PARM members that govern runtime behavior of programs in \
this lineage.

CRITICAL: Only list items present in chunk_contents or graph_paths for this lineage. \
A COBOL program calling its own paragraph via PERFORM is NOT a dependency.

Chunk contents:
{{chunk_contents}}

Graph paths:
{{graph_paths}}

Supporting data:
{{supporting_data}}

Prior section context (full JCL lineage from prior sections):
{{prior_section_drafts}}

System: {{system_id}}
""",
    },
    "jcl_analysis_gaps_and_assumptions": {
        "system": (
            "You are rigorously documenting uncertainty, gaps, and assumptions "
            "for a targeted JCL analysis. All gaps must relate to the JCL under analysis "
            "and its directly or indirectly related assets. Do not invent missing facts."
        ),
        "user": """\
List all gaps, assumptions, low-confidence items, and SME follow-up questions \
identified during this JCL analysis.

For each gap or assumption:
- State clearly what is missing or unresolved and which asset it relates to \
(JCL step, PROC, COBOL program, copybook, dataset, or PARM member).
- Identify the chunk or graph path reference that is incomplete or ambiguous.
- Categorise: [MISSING SOURCE] | [INFERRED] | [UNRESOLVED REFERENCE] | [AMBIGUOUS]
- Suggest the SME action or additional artefact needed to resolve it.

Typical gap categories for JCL analysis:
- EXEC targets that could not be matched to a retrieved PROC or PGM source.
- Programs referenced in EXECUTES_PROGRAM edges that have no COBOL chunk.
- Copybooks referenced in USES_COPYBOOK edges that were not retrieved.
- DSN values that could not be mapped to a known data store or application.
- COND code logic that is ambiguous without business context.
- PARM values whose meaning could not be determined from the source text.

Evidence items (includes structural_required and inferred flags for this lineage):
{{evidence_items}}

Overall confidence score: {{confidence}}

Prior section context (full JCL lineage drafts):
{{prior_section_drafts}}

System: {{system_id}}
""",
    },
    # ------------------------------------------------------------------
    # jcl_analysis Phase 2 — synthesis sections
    # ------------------------------------------------------------------
    "jcl_analysis_application_overview": {
        "system": (
            "You are writing an Application Overview section for a targeted JCL analysis "
            "document. Synthesise only from the verified section drafts provided. "
            "Scope the overview entirely to the JCL under analysis and its directly or "
            "indirectly related assets. Do not add facts not present in those drafts. "
            "Label any inference as [INFERRED]."
        ),
        "user": """\
Write an Application Overview for this JCL and its full asset lineage.

Include:
1. **Component inventory** — table or grouped list of: the JCL job, PROCs it invokes, \
COBOL programs executed (directly or via PROCs), copybooks expanded by those programs, \
key datasets, and PARM members. Include a count for each type.
2. **Component relationships and Execution lineage** - Highlight key relationships: 
how the JCL invokes PROCs and programs; which programs use 
which copybooks; key dataset flows between steps; PARM dependencies.
It should be a concise end-to-end flow narrative in the form of a paragraph with optional bullet points, 
not a full restatement of the prior drafts. The flow should cascade from \
JCL → PROC/PGM → COBOL → COPYBOOK/datasets, showing the major data paths in this batch run. 
3. **Scope boundaries** — what is definitively in scope, what appears to be external \
(shared utilities, external datasets), and what is unresolved.

Base this section entirely on the verified drafts below.

Prior verified section drafts (all JCL analysis Phase 1 sections):
{{prior_section_drafts}}

System: {{system_id}}
""",
    },
    "jcl_analysis_executive_summary": {
        "system": (
            "You are writing a concise Executive Summary for a targeted JCL analysis "
            "document preferrably in just one paragraph. Use only the verified section drafts provided. "
            "Be brief — aim for under 250 words. Scope the summary entirely to the "
            "JCL under analysis. Do not add facts not in the drafts."
        ),
        "user": """\
Write a concise Executive Summary for this JCL analysis.

Cover:
1. **JCL purpose** — what business problem or batch function this JCL job performs \
(1–2 sentences, drawn from the JCL and COBOL evidence).
2. **Key business capabilities** — the most important functions performed by the \
programs in this lineage (e.g. billing calculation, payment posting, reconciliation).
3. **Asset summary** — a one-line inventory: job name, X PROCs, Y programs, \
Z copybooks, N datasets.
4. **Notable risks or gaps** — one sentence summarising the most significant \
uncertainty or gap identified in the analysis.

Base this summary entirely on the verified drafts below.

Prior verified section drafts (all JCL analysis sections):
{{prior_section_drafts}}

System: {{system_id}}
""",
    },
}

# ---------------------------------------------------------------------------
# Section metadata — single source of truth for titles and generation order.
# Kept here so prompt_library remains self-contained for the prompt layer.
# planner.py defines its own DEFAULT_SECTION_ORDER (same list) to avoid a
# circular import with models.py.
# ---------------------------------------------------------------------------

SECTION_TITLES: dict[str, str] = {
    # system_appreciation document type
    "jcl_and_procs": "JCL Jobs and Procedures",
    "cobol_programs": "COBOL Programs",
    "copybooks_and_data_structures": "Copybooks and Data Structures",
    "operational_behavior": "Operational Behavior",
    "dependencies_and_integrations": "Dependencies and Integrations",
    "gaps_and_assumptions": "Gaps and Assumptions",
    "application_overview": "Application Overview",
    "executive_summary": "Executive Summary",
    # jcl_analysis document type
    "jcl_analysis_jcl": "JCL Jobs",
    "jcl_analysis_procs": "Procedures",
    "jcl_analysis_cobol": "COBOL Programs",
    "jcl_analysis_copybooks": "Copybooks and Data Structures",
    "jcl_analysis_operational_behavior": "Operational Behavior",
    "jcl_analysis_dependencies_and_integrations": "Dependencies and Integrations",
    "jcl_analysis_gaps_and_assumptions": "Gaps and Assumptions",
    "jcl_analysis_application_overview": "Application Overview",
    "jcl_analysis_executive_summary": "Executive Summary",
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
DEFAULT_ASSEMBLY_ORDER: list[str] = [
    "executive_summary",
    "application_overview",
    "jcl_and_procs",
    "cobol_programs",
    "copybooks_and_data_structures",
    "operational_behavior",
    "dependencies_and_integrations",
    "gaps_and_assumptions",
]

# Reader-facing assembly order for the jcl_analysis document type.
# Synthesis sections (executive_summary, application_overview) appear first;
# cascaded Phase 1 sections follow in logical reading order.
JCL_ANALYSIS_ASSEMBLY_ORDER: list[str] = [
    "jcl_analysis_executive_summary",
    "jcl_analysis_application_overview",
    "jcl_analysis_jcl",
    "jcl_analysis_procs",
    "jcl_analysis_cobol",
    "jcl_analysis_copybooks",
    "jcl_analysis_operational_behavior",
    "jcl_analysis_dependencies_and_integrations",
    "jcl_analysis_gaps_and_assumptions",
]

# Map from document_type → assembly order used by MarkdownDocumentAssembler.
ASSEMBLY_ORDERS: dict[str, list[str]] = {
    "system_appreciation": DEFAULT_ASSEMBLY_ORDER,
    "jcl_analysis": JCL_ANALYSIS_ASSEMBLY_ORDER,
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
