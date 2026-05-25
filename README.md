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

## Deployment order

```
1. Build and push the new image / release
2. psql "$POSTGRES_DSN" -f database/schema.sql   ← always before app start
3. Start / restart the application
```

In Kubernetes this is typically an **init container** that runs step 2 before
the main container starts.
