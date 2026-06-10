# 01 — Repo truth and boundary

- Base commit (branch point): `0ec86b9f` (merge of PR #17, V46 structured analytics foundation).
- Branch: `fix/procore-full-raw-payload-ingestion` (from `main`, clean worktree).
- Schema head: `LATEST_SCHEMA_VERSION = 46` (`src/hb_assistant/store/migrator.py`).

## Redacted replay boundary (before this change)

- `structured_analytics._normalized_payload(row)` reads `row["canonical_json_redacted"]`,
  runs the aggressive `scrub_payload()` (collapses all URLs, rewrites secret-like keys).
- `_insert_raw_payload(...)` writes `procore_endpoint_raw_payloads` with
  `source_quality='redacted_legacy_projection'`, `raw_procore_payload_persisted=0`,
  `payload_json` = the scrubbed redacted projection.
- `backfill_from_live_records(...)` labels every structured row
  `source_quality='redacted_legacy_projection'`.

Production-copy confirmation (read-only): `procore_endpoint_raw_payloads` held
**30,059 rows, all `redacted_legacy_projection` / `raw_procore_payload_persisted=0`**.

## Live full-payload boundary

- `live_sync.run_live_sync(...)` retrieves raw endpoint items into `items` (full dicts)
  before normalization. Identity is resolvable via `_record_id_of(adapter, raw)` and the
  parent-id rules (activities→schedule_id, inspection-items→list_id, N+1 children→
  `_PARENT_ID_KEY`). `procore_project_id`, `project_key`, `adapter.endpoint_id` are in scope.
- Live writes are gated by `HB_PROCORE_LIVE=1`, mapped project, `--apply`, `--sqlite-only`,
  `--confirm-live-get`, verified-endpoint fail-closed posture, and no external writeback.
- Existing receipts never emit payload bodies (`raw_body_persisted=False`).

## No-leak tooling available

- `structured_analytics.no_raw_leak_scan(paths)` and the
  `hb-assistant procore analytics no-raw-leak-scan --path` CLI surface.
- The package `scripts/procore_full_raw_probe.py` prints source-quality distribution and
  payload field names + hash prefixes only (no bodies).

## Continue criteria (all satisfied)

- Reprocess used redacted legacy payloads (confirmed).
- Live sync has access to full item payloads (confirmed).
- Implementation validated on `/tmp` DB copies + fixtures (confirmed).
- Production DB not required for implementation validation (confirmed).
