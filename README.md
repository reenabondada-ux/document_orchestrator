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

Run the following from the project root. This creates `.venv/` inside the repo,
keeping dependencies isolated to this project.

```bash
cd document_orchestrator_repo
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

### 4. Apply the database schema

Schema management is intentionally separate from the application. The app never
runs DDL at startup.

```bash
psql "$POSTGRES_DSN" -f database/schema.sql
```

All statements are idempotent (`IF NOT EXISTS`), so re-running is safe.

**When the schema needs to change**, add a numbered SQL file under
`database/migrations/` (for example `0001_add_column_x.sql`) containing only the
incremental DDL, then run:

```bash
python scripts/migrate.py
python scripts/migrate.py --dsn "postgresql://..."
```

`migrate.py` applies `schema.sql` first, then every file in
`database/migrations/` in lexicographic order. Write each migration
idempotently (`ADD COLUMN IN NOT EXISTS`, etc.) so re-runs are safe.

### 5. Start the API

```bash
uvicorn mainframe_doc_orchestrator.api.app:app --host 0.0.0.0 --port 8010 --reload
```

Once running, the API is available at:

| Resource | URL |
|---|---|
| API base | `http://localhost:8010` |
| Interactive docs (Swagger UI) | `http://localhost:8010/docs` |
| OpenAPI schema (JSON) | `http://localhost:8010/openapi.json` |
| Dashboard | `http://localhost:8010/documents/dashboard` |

## API surface

### User-facing endpoints in Swagger UI

| Method | Path | Description |
|---|---|---|
| `POST` | `/documents` | Create a new document run; optionally bulk-generate all sections with `auto_generate=true` |
| `POST` | `/documents/{run_id}/generate-all` | Generate all pending sections in one synchronous call |
| `POST` | `/documents/{run_id}/generate` | Generate the next pending section |
| `POST` | `/documents/{run_id}/sections/{section_name}/approve` | Approve a section |
| `POST` | `/documents/{run_id}/sections/{section_name}/regenerate` | Regenerate a section |
| `POST` | `/documents/{run_id}/export` | Export the final document |

### Dashboard/backing endpoints

These endpoints are still implemented, but hidden from Swagger/OpenAPI because
the primary user flow is now create → review in dashboard → approve/regenerate → export.

- `GET /documents`
- `GET /documents/{run_id}`
- `GET /documents/{run_id}/sections`
- `GET /documents/{run_id}/sections/{section_name}`
- `GET /documents/{run_id}/retrieval-passes`
- `GET /documents/{run_id}/events`
- `GET /documents/dashboard`
- `GET /documents/{run_id}/preview`

See [docs/API.md](docs/API.md) for full request/response details.

## Endpoint invocation sequence

The workflow is **stateful**. Sections must be generated in plan order because the
Phase 2 synthesis sections (`application_overview`, `executive_summary`) depend
on Phase 1 sections being at least `review_ready` or `approved`.

### Option A — create and generate everything in one call

```
1.  POST /documents
        Body: include "auto_generate": true
        → creates the run
        → generates all pending sections synchronously in plan order
        → returns run status only (not inline section drafts)
        → if an intermediate section fails, the response still returns the run
          plus auto_generate_errors so processing can resume later from that point

2.  Review results in the dashboard / preview links

3.  POST /documents/{run_id}/sections/{section_name}/approve
        (or /regenerate if the draft needs another pass)

4.  POST /documents/{run_id}/export
        → returns the assembled Markdown document.
```

### Option B — create first, then generate later

```
1.  POST /documents
        Body: see example payload below
        → returns run_id and initial run status

2a. POST /documents/{run_id}/generate-all
        → generates all remaining pending sections synchronously
        → stops on first failing section and returns partial progress

2b. Or repeat manually:
        POST /documents/{run_id}/generate
        → generates the next pending section in generation order:
              jcl_and_procs → cobol_programs → copybooks_and_data_structures
              → operational_behavior → dependencies_and_integrations → gaps_and_assumptions
              → application_overview → executive_summary

3.  Review results in the dashboard / preview links

4.  Approve or regenerate sections as needed

5.  POST /documents/{run_id}/export
        → returns the assembled Markdown document.
        Sections are ordered for reading: Executive Summary → Application Overview
        → detail sections (JCL/PROC, COBOL, Copybooks, Operational, Dependencies, Gaps).
```

> **Tip:** `POST /documents/{run_id}/generate` always picks the next pending section
> automatically — you do not need to specify the section name.

> **Bulk generation behaviour:** `auto_generate=true` on `POST /documents` and
> `POST /documents/{run_id}/generate-all` are intentionally long-running,
> synchronous calls. If a section fails, previously generated sections remain
> persisted and the response includes `auto_generate_errors` so you can fix the
> issue and retry from that point later.

## Example payloads

### System appreciation document — `POST /documents`

```json
{
  "system_id": "MAINFRAME_POC_ESTATE",
  "document_type": "system_appreciation",
  "topic": "Analyse and document mainframe POC estate",
  "complexity": "complex",
  "auto_generate": true,
  "filters": {
    "asset_types": ["JCL", "PROC", "COBOL", "COPYBOOK", "PARM"]
  },
  "metadata": {
    "output_format": "markdown",
  }
}
```

### JCL analysis document — `POST /documents`

```json
{
  "system_id": "JCL_ANALYSIS_BILLRUN1",
  "document_type": "jcl_analysis",
  "topic": "Analyse billing flow in BILLRUN1 JCL",
  "complexity": "medium",
  "auto_generate": false,
  "filters": {
    "asset_types": ["JCL", "PROC", "COBOL", "COPYBOOK", "PARM"],
    "asset_ids": ["JCL__BILLRUN1"]
  }
}
```

## Field notes

- `complexity` — convenience hint that drives `top_k_chunks` and `top_k_paths` values (`simple`→10, `medium`→20, `complex`→35).
- `auto_generate` — when `true`, `POST /documents` immediately generates all pending sections in plan order before returning.
- `filters.asset_types` — plan-level allow-list; each section's `asset_type_filter` in the blueprint narrows this further at retrieval time.
- `filters.asset_ids` — leave empty for broader semantic scope; populate only for targeted runs against a known asset set.
- `metadata` — optional pass-through bag for run metadata such as `output_format`, `prior_run_ids`, or source bundle identifiers.
- `retrieval_request` — not part of the payload. Retrieval happens per section during `generate`, `generate-all`, or `create` when `auto_generate=true`.
- `DocumentRunResponse.auto_generate_errors` — populated only when bulk generation hits an intermediate failure and returns partial progress.

## Deployment order

```
1. Build and push the new image / release
2. psql "$POSTGRES_DSN" -f database/schema.sql
3. Start / restart the application
```

In Kubernetes this is typically an init container that runs step 2 before the
main container starts.
