# Procore Full Raw Payload Ingestion Package

## Purpose

This package is for Bobby's local code agent. It implements the change from redacted Procore replay to fully populated Procore raw/structured analytics storage.

Repository: `RMF112018/hb-personal-assistant`

Local repo path: `/Users/bobbyfetting/hb-personal-assistant`

Package path after copying into the repo:

`docs/planning/procore_full_raw_payload_ingestion_package/README.md`

Objective:

- Persist full Procore endpoint response payload bodies into the private local SQLite DB.
- Populate `procore_endpoint_raw_payloads` and all matching `procore_raw_*` structured tables from those full endpoint payload values.
- Stop using `procore_live_records.canonical_json_redacted` as the source for useful Procore analytics except as an explicitly degraded fallback.
- Prevent degraded legacy replay from overwriting full live payload rows.
- Keep redaction only at outbound/reporting boundaries: CLI stdout, logs, repo evidence, browser/status JSON, Obsidian, daily brief, test snapshots, and committed docs.

## Why this package exists

PR #17 added the V46 Procore structured analytics foundation. It correctly created raw landing/control tables and endpoint-family `procore_raw_*` tables, but its bootstrap path still derives payloads from `procore_live_records.canonical_json_redacted`. That makes the new raw/structured tables present but not fully useful: redacted legacy payloads turn many business fields into `NULL`, placeholders, or missing values.

Bobby's requirement is different: the local/private production SQLite DB is the system of record and should preserve full Procore endpoint business payload values. Redaction is useful only for content leaving the DB.

## Current repo-truth to verify

The agent must verify these before editing:

1. `src/hb_assistant/procore/structured_analytics.py`
   - `_normalized_payload()` currently reads `canonical_json_redacted`.
   - `_insert_raw_payload()` inserts that redacted/scrubbed JSON into `procore_endpoint_raw_payloads`.
   - `backfill_from_live_records()` labels rows `source_quality=redacted_legacy_projection`.
   - legacy rows set `raw_procore_payload_persisted=0`.

2. `src/hb_assistant/procore/live_sync.py`
   - `run_live_sync()` has access to live endpoint item payloads before normalization/upsert.
   - live execution is already gated by `HB_PROCORE_LIVE=1`, `--apply`, `--sqlite-only`, and `--confirm-live-get`.
   - existing receipts must not emit raw payload bodies.

3. `src/hb_assistant/cli/procore.py`
   - `procore analytics reprocess` is local-only and should remain stable.
   - `procore live sync` is the live endpoint GET path.
   - `structured-counts`, `coverage`, and `no-raw-leak-scan` are operator verification surfaces.

4. `src/hb_assistant/store/migrator.py`
   - current schema head is V46.
   - add V47 only if current columns cannot safely express source-quality/provenance semantics.

## Non-negotiable requirements

### Full raw DB storage

The private local DB must store full Procore endpoint response item JSON in `procore_endpoint_raw_payloads.payload_json`.

Allowed in private DB:

- nested Procore business objects;
- business text;
- people/company references;
- dates/statuses;
- financial values;
- custom fields;
- attachment metadata;
- all endpoint-specific fields needed for analytics.

Never store transport/auth secrets:

- Authorization headers;
- bearer tokens;
- OAuth access tokens;
- OAuth refresh tokens;
- client secrets;
- API keys;
- local credential-cache contents.

### Redaction boundary

Redaction applies only when data leaves the DB boundary. Do not emit raw payload bodies to:

- Git/repo evidence;
- CLI stdout;
- logs;
- browser/status JSON;
- Obsidian;
- daily brief;
- test snapshots;
- committed docs.

### Source-quality precedence

Implement deterministic precedence:

1. `live_full_payload`
2. `fixture_full_payload` / test equivalent
3. `redacted_legacy_projection`
4. unknown/empty

Higher-quality rows win. Legacy replay must not overwrite full raw payload rows or structured rows derived from full raw payloads.

### Legacy fallback

Keep legacy replay available because old DBs may only have `procore_live_records`, but classify it honestly:

- `source_quality='redacted_legacy_projection'`;
- `raw_procore_payload_persisted=0`;
- degraded fallback only;
- never allowed to downgrade full payload data.

## Prompt sequence

Execute in order:

1. `prompts/00_REPO_TRUTH_AND_BRANCH_GUARD.md`
2. `prompts/01_SCHEMA_AND_SOURCE_QUALITY_STRATEGY.md`
3. `prompts/02_RAW_PAYLOAD_PERSISTENCE_API.md`
4. `prompts/03_LIVE_SYNC_INTEGRATION.md`
5. `prompts/04_STRUCTURED_PROJECTION_FROM_FULL_RAW.md`
6. `prompts/05_LEGACY_REPLAY_PRECEDENCE_AND_CLI.md`
7. `prompts/06_VALIDATION_AND_EVIDENCE.md`
8. `prompts/07_FINAL_HANDOFF.md`

## Preferred implementation shape

- `src/hb_assistant/procore/structured_analytics.py`
  - shared full raw persistence helper;
  - structured projection from payload helper;
  - source-quality rank/precedence;
  - legacy fallback support;
  - coverage/source-quality diagnostics.

- `src/hb_assistant/procore/live_sync.py`
  - call full raw persistence + structured projection at live sync boundary for each retrieved item.
  - preserve all live guardrails.

- `src/hb_assistant/cli/procore.py`
  - keep existing command names stable.
  - enhance receipts/coverage if useful.

- `src/hb_assistant/store/migrator.py`
  - add V47 only if needed.

- tests:
  - full raw fixture persistence;
  - live sync fixture integration;
  - structured field population from full payload;
  - source-quality downgrade prevention;
  - no raw body emitted to stdout/evidence.

## Required evidence bundle

Write scrubbed evidence under:

`docs/evidence/procore_full_raw_payload_ingestion/`

Required evidence files:

- `README.md`
- `01-repo-truth.md`
- `02-schema-source-quality.md`
- `03-full-raw-fixture-proof.md`
- `04-live-sync-boundary.md`
- `05-structured-null-rate-matrix.md`
- `06-idempotency-and-precedence.md`
- `07-no-leak-scan.md`
- `08-validation-results.md`
- `09-operator-production-runbook.md`
- `10-final-handoff.md`

Evidence may include counts, hashes, field names, percentages, and classifications. Evidence must not include raw payload bodies, DB files, private text values, secrets, signed URLs, or token-like values.

## Validation acceptance

Before commit, prove:

- full raw endpoint payload rows can be inserted from fixture live response objects;
- `payload_json` in DB preserves fixture business fields;
- structured rows populate fields that redacted replay leaves `NULL`;
- legacy replay cannot overwrite full payload rows;
- legacy replay cannot downgrade full-derived structured rows;
- financial amount extraction still passes;
- live sync receipts do not include payload bodies;
- no raw payload files are committed;
- production DB is untouched during validation.

## Suggested branch and commit

Branch:

`fix/procore-full-raw-payload-ingestion`

Commit message:

`fix(procore): populate raw tables from full endpoint payloads`
