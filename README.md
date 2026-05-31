# Mainframe Document Orchestrator

Turns retrieval evidence packs into a System Appreciation Document via a
multi-step LLM workflow with Postgres-backed state.

## Repository structure

```
database/
  schema.sql          # Postgres DDL — apply before first deploy (see below)
mainframe_doc_orchestrator/
  api/                # FastAPI app, lifespan, dependencies, route handlers
  clients/            # LLM and retrieval adapters
  persistence/        # Postgres repositories (AsyncConnectionPool)
  services/           # Workflow engine, prompt engine, draft writer, exporter
  schemas/            # JSON schema artifacts
docs/                 # Architecture and API documentation
tests/
```

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- A running instance of the mainframe retrieval API (see `RETRIEVAL_ENDPOINT` in `.env`)

## Setup

### 1. Create and activate a virtual environment

Run the following from the **project root** (`document_orchestrator_repo/`). This creates `.venv/` inside the repo, keeping dependencies isolated to this project and separate from any other projects on your machine.

```bash
cd document_orchestrator_repo   # ensure you are in the project root
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

Dependencies are declared in `pyproject.toml`. Install the package in editable mode:

```bash
pip install -e .
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — set POSTGRES_DSN and any LLM provider credentials
```

### 4. Apply the database schema (pre-deploy, run once)

Schema management is intentionally **separate from the application**.
The app never runs DDL at startup — it only opens a connection pool.

```bash
psql "$POSTGRES_DSN" -f database/schema.sql
```

All statements are idempotent (`IF NOT EXISTS`), so re-running is safe.

**When the schema needs to change**, add a numbered SQL file under `database/migrations/`
(e.g. `0001_add_column_x.sql`) containing only the incremental DDL, then run the
migration script instead of plain `psql`:

```bash
python scripts/migrate.py          # reads POSTGRES_DSN from .env
python scripts/migrate.py --dsn "postgresql://..."  # explicit override
```

`migrate.py` applies `schema.sql` (no-op if already up to date) followed by every
file in `database/migrations/` in lexicographic order.  Write each migration
idempotently (`ADD COLUMN IF NOT EXISTS`, etc.) so re-runs are safe.

### 5. Start the API

```bash
uvicorn mainframe_doc_orchestrator.api.app:app --host 0.0.0.0 --port 8002 --reload
```

Once running, the API is available at:

| Resource | URL |
|---|---|
| API base | `http://localhost:8002` |
| Interactive docs (Swagger UI) | `http://localhost:8002/docs` |
| OpenAPI schema (JSON) | `http://localhost:8002/openapi.json` |

**Endpoints:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/documents` | Create a new document run |
| `GET` | `/documents` | List all runs |
| `GET` | `/documents/{run_id}` | Get a run |
| `POST` | `/documents/{run_id}/generate` | Generate the next pending section |
| `GET` | `/documents/{run_id}/sections` | List section drafts |
| `GET` | `/documents/{run_id}/sections/{section_name}` | Get a specific section |
| `POST` | `/documents/{run_id}/sections/{section_name}/approve` | Approve a section |
| `POST` | `/documents/{run_id}/sections/{section_name}/regenerate` | Regenerate a section |
| `GET` | `/documents/{run_id}/retrieval-passes` | List retrieval passes for a run |
| `GET` | `/documents/{run_id}/events` | View lifecycle events |
| `POST` | `/documents/{run_id}/export` | Export the final document |

See [docs/API.md](docs/API.md) for full request/response details.

## Endpoint invocation sequence

The workflow is **stateful** — sections must be generated in the correct order
because Phase 2 synthesis sections (`application_overview`, `executive_summary`)
depend on Phase 1 drafts being approved first.

```
1.  POST /documents
        Body: see example payload below
        → returns run_id

2.  Repeat until all Phase 1 sections are review_ready:
        POST /documents/{run_id}/generate
        → generates the next pending section in generation order:
              jcl_and_procs → cobol_programs → copybooks_and_data_structures
              → operational_behavior → dependencies_and_integrations → gaps_and_assumptions
        GET  /documents/{run_id}/sections/{section_name}   ← review the draft
        POST /documents/{run_id}/sections/{section_name}/approve
             (or /regenerate if the draft needs another pass)

3.  Once all six Phase 1 sections are approved, repeat step 2 for Phase 2:
              application_overview → executive_summary
        These sections synthesise from the approved Phase 1 drafts; no fresh
        retrieval is performed. The dependency guard will reject a generate call
        if any required Phase 1 section is not yet review_ready or approved.

4.  POST /documents/{run_id}/export
        → returns the assembled Markdown document.
        Sections are ordered for reading: Executive Summary → Application Overview
        → detail sections (JCL/PROC, COBOL, Copybooks, Operational, Dependencies, Gaps).
```

> **Tip:** `POST /documents/{run_id}/generate` always picks the next pending section
> automatically — you do not need to specify the section name. Call it in a loop
> until `GET /documents/{run_id}` shows `status: complete`.

### Example payload to generate system appreciation document — POST /documents

```json
{
  "system_id": "ACME_BILLING_ESTATE",
  "document_title": "ACME Billing & Payment System — System Appreciation Document",
  "document_type": "system_appreciation",
  "user_role": "analyst",
  "topic": "Monthly billing, daily payment application, and reconciliation control flows across BILLRUN1, PMTRUN7, and CTRLJOB",
  "jcl_complexity": "medium",
  "top_k_chunks": 10,
  "filters": {
    "asset_types": ["JCL", "PROC", "COBOL", "COPYBOOK", "PARM"],
    "asset_ids": [],
    "domains": ["billing", "payments", "reconciliation"]
  },
  "metadata": {
    "output_format": "markdown",
    "prior_run_ids": [],
    "source_bundle": "mainframe_poc_bundle"
  }
}
```

### Example payload to generate a JCL analysis document - POST /documents

``` json
{
  "system_id": "JCL_ANALYSIS_BILLRUN1",
  "document_type": "jcl_analysis",
  "user_role": "analyst",
  "topic": "Analyse billing flow in BILLRUN1 JCL",
  "jcl_complexity": "medium",
  "top_k_chunks": 10,
  "filters": {
    "asset_types": ["JCL", "PROC", "COBOL", "COPYBOOK", "PARM"],
    "asset_ids": ["JCL__BILLRUN1"]
  }
}
```

**Field notes:**
- `jcl_complexity` — convenience hint that drives `top_k_paths` when `top_k_paths` is not explicitly set (`simple`→9, `medium`→15, `complex`→25). Use `"complex"` for jobs with 5+ steps or many copybooks.
- `top_k_chunks` — chunks retrieved per section. 10 gives solid coverage across all asset types without overwhelming context.
- `filters.asset_types` — plan-level allow-list; each section's `asset_type_filter` in the blueprint narrows this further at retrieval time (e.g. the copybooks section will only retrieve `COPYBOOK` chunks regardless of what is listed here).
- `filters.asset_ids` — leave empty to let the semantic query and `asset_types` do the scoping. Populate only for targeted regenerate passes against a specific known asset set.
- `retrieval_request` — **not** part of the payload. `POST /documents` only creates the plan; the RAG retrieval service is called once per section inside each `POST /documents/{run_id}/generate` invocation.

## Deployment order

```
1. Build and push the new image / release
2. psql "$POSTGRES_DSN" -f database/schema.sql   ← always before app start
3. Start / restart the application
```

In Kubernetes this is typically an **init container** that runs step 2 before
the main container starts.
