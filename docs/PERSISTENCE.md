# Persistence

The orchestrator stores document state in Postgres using two tables:

- `document_runs`
- `retrieval_passes`

The full section plan is stored in `document_runs.plan` as JSONB, including section status, draft content, confidence, notes, and retrieval request references.

The `retrieval_passes` table records each retrieval attempt with `pass_number`, `query`, `request_id`, and status.
