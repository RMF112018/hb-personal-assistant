# 01 — Repo Truth, DB Audit Replay, and Schema Baseline

## Objective

Establish the exact live repo, branch, schema, and DB state before implementation. Recreate the safe DB-copy audit locally and produce evidence without dumping private data.

## Required steps

1. Verify branch, HEADs, dirty tree, recent branches, recent PR/merge activity visible from git history, and whether `config/config.yml` exists/tracked.
2. Create a timestamped `/tmp` SQLite `.backup` of the production DB.
3. Open the copied DB in read-only URI mode and set `PRAGMA query_only=ON`.
4. Verify integrity and quick checks.
5. Inventory all Procore, raw-content, daily-brief, retrieval, and candidate tables.
6. Compare current findings against the DB audit package findings captured in `AUDIT_SUMMARY.md`.

## Required DB queries

Capture safe counts only: all table row counts, all `procore_%` table schemas and row counts, all `%raw_content%` table schemas and row counts, all `%daily_brief%` table schemas and row counts, all `%candidate%` table schemas and row counts, all `retrieval_%` table schemas and row counts, endpoint distribution from `procore_live_records`, signal distribution from `procore_action_signals`, and current `schema_migrations` head.

Do not dump raw payload values, raw JSON, raw text, raw URLs, names, emails, tokens, or private record content.

## Required analysis

Classify every existing Procore table as `raw_landing`, `structured_bronze`, `normalized_silver`, `gold_read_model`, `signal_only`, `legacy`, or `unknown`.

Classify current endpoint-family coverage as `analytics_ready_structured`, `projection_only`, `redacted_summary_only`, `hash_only`, `generic_json_only`, or `missing`.

## Evidence

Write evidence under `docs/evidence/procore_endpoint_structured_analytics_foundation/01-db-audit-and-schema-baseline/`.

Include safe command log, safe row counts, schema map, endpoint distribution, signal distribution, storage-layer classification matrix, gap summary, and proof no production DB mutation occurred.

## Stop conditions

Stop if DB backup fails, integrity/quick check fails, repo tree is unsafe, or the schema cannot be reliably inspected.
