-- =============================================================================
-- Mainframe Document Orchestrator — Postgres schema
--
-- Apply this file BEFORE starting the application:
--
--   psql "$POSTGRES_DSN" -f database/schema.sql
--
-- All statements are idempotent (IF NOT EXISTS), so re-running is safe.
-- When the schema needs to change (column add/drop/rename), add a new migration
-- file under database/migrations/ and apply it the same way, in order.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- document_runs
-- One row per document generation run.  The `plan` column stores the full
-- section plan as JSONB so sections can be queried and patched in-place
-- without a separate sections table.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_runs (
    run_id          TEXT        PRIMARY KEY,
    document_title  TEXT        NOT NULL,
    system_id       TEXT        NOT NULL,
    plan            JSONB       NOT NULL,          -- full section plan with per-section state
    status          TEXT        NOT NULL,          -- created | in_progress | review_ready | approved | exported
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ NULL,              -- set on export
    export_artifact JSONB       NULL               -- {format, content} on export
);

-- ---------------------------------------------------------------------------
-- retrieval_passes
-- One row per retrieval call made during section generation.  Linked to
-- document_runs for cascade delete.  Used by the orchestrator for crash
-- recovery (re-fetch evidence pack by evidence_request_id without re-triggering retrieval).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS retrieval_passes (
    pass_id      TEXT    PRIMARY KEY,
    run_id       TEXT    NOT NULL REFERENCES document_runs(run_id) ON DELETE CASCADE,
    section_name TEXT    NOT NULL,
    pass_number  INTEGER NOT NULL,                 -- 1-based counter per (run_id, section_name)
    query        TEXT    NOT NULL,
    evidence_request_id   TEXT    NULL,            -- evidence pack id; NULL while in_progress
    status       TEXT    NOT NULL,                 -- in_progress | completed | failed
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_document_runs_system_id        ON document_runs(system_id);
CREATE INDEX IF NOT EXISTS idx_document_runs_status           ON document_runs(status);
CREATE INDEX IF NOT EXISTS idx_retrieval_passes_run_id        ON retrieval_passes(run_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_passes_evidence_request_id ON retrieval_passes(evidence_request_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_passes_section_name  ON retrieval_passes(section_name);
