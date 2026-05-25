# Remediation: DB Readiness And Structured Dry-Run Blocking (Addendum Prompt 03)

Date: 2026-05-25

## Context

Runtime commands `files ingest --dry-run --json` and `run morning --dry-run --json` failed with raw SQLite open errors when the DB directory was not writable.

## Decisions

- Added explicit DB readiness checks in `PathPolicy.ensure_db_ready()`.
- Added typed `StoreReadinessError` for structured store/runtime DB failures.
- Hardened store connection setup to fail with structured readiness payloads rather than raw `OperationalError`.
- Dry-run command paths now return actionable JSON `status: "blocked_db_unavailable"` with repair guidance.
- `run morning --dry-run --json` reports orchestrator stage skip details when DB is blocked.

## Behavior

- DB readiness verifies app support path, DB parent validity/writability, SQLite openability, and WAL probe state.
- `files ingest --dry-run --json` preserves `no_provenance_candidates` behavior when DB is available, otherwise returns structured DB blocked JSON.
- `run morning --dry-run --json` returns structured blocked JSON with `orchestrator.stages` skip metadata instead of traceback.

## Validation

Evidence and required command outputs are captured in:

- `docs/evidence/remediation-addendum/prompt-03/`
