# Tests

New N8C-5 tests (44 total, FakeModelProvider only — no live Ollama):
- `tests/test_enrichment_models.py` (10) — pure result validators, size caps, oversized rejection,
  deterministic compute_job_id.
- `tests/test_enrichment_repository.py` (14) — migration/CHECKs, idempotent enqueue, payload cap,
  atomic claim (single + two-connection), heartbeat, expired-lease release, ownership-gated complete,
  fail requeue-then-exhaust, read-only peek.
- `tests/test_enrichment_worker.py` (9) — run_once summary/claims, candidate/unreviewed-only ingest,
  read-only dry_run, digest-drift/deleted/ambiguous -> stale_rejected, oversized -> fail, backlink
  store-only no-vault-mutation, reserved job type refused.
- `tests/test_enrichment_no_autostart.py` (6) — import-writes-nothing, startup-enqueues-nothing,
  worker-not-in-lifespan, no remote MCP enrichment tool, writes-only-enrichment-tables, provider no
  top-level requests import.
- `tests/test_fastapi_analytics_enrichment.py` (5) — read-only GET jobs/receipts, filters, 404,
  no write route.

Guard tests updated: `test_schema_version_head_consistency::test_v101_migration_row_present`;
`test_source_identity_v99_migration::test_latest_schema_version_is_101`.

Result: 44 N8C-5 + 216-test N8C regression bundle (N8C-5+N8C-4+N8C-3+N8C-2+N8C-1) all pass, exit 0.
Ruff clean on all new modules; api.py ruff error count unchanged vs base (delta 0). Schedule migrator
canary (`scripts/test-schedule.sh`) exit 0.
