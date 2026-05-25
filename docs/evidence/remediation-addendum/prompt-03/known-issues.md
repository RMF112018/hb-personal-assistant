# Addendum Prompt 03 Known Issues

## Runtime blockers observed in this run

1. `hb-assistant files ingest --dry-run --json` is blocked because DB parent path is not writable in current local environment.
2. `hb-assistant run morning --dry-run --json` is blocked for the same DB readiness reason.

These are now reported as structured JSON (`status: "blocked_db_unavailable"`) with readiness checks and repair guidance.
