# 200 — Procore Full Raw Payload Ingestion

**Objective:** make `procore_endpoint_raw_payloads.payload_json` and the matching
`procore_raw_*` structured tables carry the **full** Procore endpoint response item
values, sourced from live endpoint payloads, instead of the redacted legacy projection
replayed from `procore_live_records.canonical_json_redacted`.

## Problem

The V46 structured-analytics foundation (PR #17) created the raw landing table and 43
endpoint-family structured tables, but its only populate path
(`backfill_from_live_records`) derived payloads from `canonical_json_redacted` — a
redacted legacy projection. `scrub_payload()` collapses every URL and rewrites
secret-like keys, so the structured tables were present but business-poor: amounts,
owners, dates, cost codes and nested objects landed `NULL`/`[scrubbed]`. On the
production copy this is visible as **30,059 rows, all `redacted_legacy_projection`,
`raw_procore_payload_persisted=0`**.

Bobby's requirement: the private local SQLite DB is the system of record and must
preserve full Procore business payloads. Redaction belongs only at outbound surfaces
(CLI stdout, logs, repo evidence, browser/status JSON, Obsidian, daily brief, test
snapshots, committed docs). Transport/auth secrets must never be stored anywhere.

## Design

No schema change — V46 already carries `source_quality`,
`raw_procore_payload_persisted`, full-business structured columns and a
`CHECK(external_writeback_performed = 0)`. The change is application-level.

### Full-raw persistence API (`procore/structured_analytics.py`)

`upsert_full_raw_payload_and_structured(...)` writes one full endpoint item to
`procore_endpoint_raw_payloads` (`payload_json` = the full item with transport secrets
removed, `raw_procore_payload_persisted=1`, `redaction_status='full_business_payload'`)
and projects the matching `procore_raw_*` row via `_structured_values_from_payload(...)`.
The raw row is inserted before the structured row (FK ordering under
`PRAGMA foreign_keys=ON`). It accepts an existing `conn` or opens its own `db_path`
connection + transaction.

- **Transport-only scrubber** `scrub_transport_secrets()` — drops keys matching
  `AUTH_SECRET_KEY_RE` (authorization, bearer/access/refresh tokens, client/app secret,
  api key, password, private key) and strips signed-URL credential query params
  (`X-Amz-*`, `SharedAccessSignature`, `sig`/`signature`/`token`/`key`/…), preserving
  every other business value (people, companies, financials, nested objects, attachment
  metadata, custom fields). It is deliberately narrower than `scrub_payload()` (left
  untouched for the legacy/outbound path). A narrow post-scrub assertion
  `_has_transport_secret()` refuses to persist if any credential survived — unlike
  `payload_has_forbidden_security_artifact()`, which flags *all* https URLs and so
  cannot gate a full business payload.
- **Placeholder cleaning** `_clean_scalar()` treats `null`/`none`/`[redacted]`/
  `[scrubbed]`/`""`/`{}`/`[]` as missing for structured scalar extraction, without
  mutating the stored full `payload_json`. `_scalarize()` reduces a nested object
  (`wbs_code`, `created_by`, …) to a representative scalar for the TEXT column.

### Source-quality precedence

`SOURCE_QUALITY_RANK = {live_full_payload:100, fixture_full_payload:90,
redacted_legacy_projection:10}`. Higher rank wins; equal rank is an idempotent upsert;
a lower rank never overwrites/downgrades. The anchor is the structured `record_key`
(which excludes `payload_hash`, unlike `raw_payload_id`): before a write,
`_existing_source_quality_rank()` is compared to the incoming rank. The legacy
`backfill_from_live_records` additionally checks `_existing_raw_full_rank()` and skips
records already covered by a full raw row, reporting `skipped_due_to_higher_quality`.

### Live-sync integration (`procore/live_sync.py`) — raw-first

For each retrieved item (main loop **and** inline N+1 children), `run_live_sync` resolves
a stable `record_id` + parent id and calls the full-raw API **before** any lossy/
normalized projection (`upsert_procore_live_record`, history, `project_*`), so a
normalize/projection failure cannot lose business fields. Per-item failures isolate
(loop continues) but increment `raw_persist_error_count`; the run verdict is degraded
(`state="degraded_raw_persistence"`, `ok=false`) whenever `raw_persist_error_count > 0`
and rows were retrieved. The receipt gains `raw_payload_rows_written`,
`structured_rows_written`, `raw_persist_error_count`, `full_raw_persistence_enabled`,
`raw_payload_body_emitted_to_stdout=false` — and never carries a payload body. All
existing gates (`HB_PROCORE_LIVE`, mapped project, `--apply`, `--sqlite-only`,
`--confirm-live-get`, verified-endpoint fail-closed, no external writeback) are preserved.

### Structured source order + CLI (`cli/procore.py`)

`backfill_from_raw_payloads(...)` projects structured rows from full raw rows
(`raw_procore_payload_persisted=1`). `procore analytics reprocess` defaults to
`--source auto`: project full raw rows first, then redacted legacy as fallback for
records with no full payload (legacy is guarded to never downgrade). `--source full|legacy`
select a single path. Top-level receipt keys (`structured_written`, `raw_landing_written`,
`source_quality`, `live_procore_calls`, `external_writeback_performed`, `mode`) are
preserved for back-compat. `structured-counts`/`coverage` gained `by_source_quality`,
`raw_persisted`, `legacy_fallback`, and `degraded` diagnostics (counts only, no bodies).

## Guardrails

Redaction stays at outbound boundaries only; the private DB keeps full business
payloads. Transport/auth secrets are never stored. No external writeback
(`external_writeback_performed=0`, CHECK-enforced). No payload bodies in receipts,
stdout, logs, evidence, or snapshots. Validation runs on `/tmp` DB copies; production
DB is read-only during validation.

## Evidence

`docs/evidence/procore_full_raw_payload_ingestion/` (scrubbed: counts, hashes, field
names, percentages, classifications — no payload bodies).
