# 242 — Scheduled Procore Full Pipeline Refresh

## Behavior

The production `daily-source-refresh` scheduler runs at `20:00` local time and passes
`RefreshOptions.procore_project_scope` / `procore_project_keys` into
`SourceRefreshOrchestrator`. Production configuration must set:

```yaml
automation:
  scheduler:
    procore_project_scope: "all_mapped"
    procore_project_keys: []
```

`all_mapped` includes every Procore registry row whose status is live-refresh eligible.
The eligible statuses are exactly `pilot` and `active`. `pending`, `deprecated`,
missing-ID, unknown, and allowlist-excluded projects are never refreshed silently; they
are emitted in the receipt with reason codes. If `procore_project_keys` contains an
unknown or unsafe key, the run blocks before live Procore reads.

## Pipeline

When production scheduler live reads are enabled, Procore remains GET-only behind
`HB_PROCORE_LIVE=1` and local SQLite is the only mutation target. After the canonical
`procore_live_*` refresh, the orchestrator runs the in-process projection pipeline:

1. Verify raw-payload freshness in `procore_endpoint_raw_payloads` (see
   *v2 — Precise raw-payload freshness taxonomy* below for the per-endpoint classification).
2. Run `SQLiteMigrator.apply()` for V48 projection schema reconciliation.
3. Run `projection_schema_audit`.
4. Run endpoint-specific projection replay with `MODE_ENFORCE`.
5. Run `projection_audit`.

Projection replay is skipped and the scheduled run is marked degraded if raw full-payload
freshness is missing or schema parity is broken. Projection replay or audit failures are
never hidden behind a green scheduler status.

## Receipt

The scheduler receipt includes `procore_projection_summary` with:

- selected and skipped project counts plus per-project reason metadata;
- `raw_full_payload_freshness` with the per-endpoint status taxonomy (see v2 section);
- `raw_full_rows_by_project` and `raw_full_rows_by_project_endpoint`;
- projection schema audit ok/mismatch counts;
- projection replay ok and primary/child row counts;
- projection audit ok, unknown business field count, and runtime schema mismatch count;
- guardrails showing no live projection calls, no external writeback, and no emitted values.

Receipts and evidence are metadata-only: no raw payload values, tokens, signed URLs, or
source-system writeback are emitted.

## Operator Inspection

Inspect the last scheduled receipt with:

```bash
hb-assistant scheduler status daily-source-refresh --environment production --json
```

## v2 — Precise raw-payload freshness taxonomy

### Why

The v1 freshness gate (`_verify_procore_raw_payload_freshness`) re-queried
`procore_endpoint_raw_payloads` filtered by `capture_run_id IN (this run's sync_run_ids)`.
But `structured_analytics._insert_full_raw_payload` uses
`ON CONFLICT(raw_payload_id) DO UPDATE` whose SET clause **does not refresh
`capture_run_id`**. On an idempotent daily re-run, unchanged records (same `payload_hash`
→ same `raw_payload_id`) are updated in place (`is_current=1`, `payload_seen_last_utc`
refreshed) but keep their **original** run's `capture_run_id`. The gate therefore counted
0 rows for those endpoints and degraded the run even though every record was present and
current — the production `2026-06-09` `missing_fresh_raw_payload_count = 21` defect (rfis,
submittals, change-events, …, all with real retrieved counts and current landed rows).

### Fix — presence-based, replay-aligned gate

The gate now mirrors projection replay's own selection: it counts **current
`live_full_payload` rows per `(project_key, endpoint_key)`** with
`raw_procore_payload_persisted=1 AND is_current=1 AND source_quality='live_full_payload'`,
**without** any `capture_run_id` filter (`_current_live_full_payload_counts`). Landing is
proven by presence of the exact rows replay consumes. The `capture_run_id`-not-refreshed
quirk is a known nuance; the gate no longer depends on it. No `live_sync` change, no
migration, and no new `source_quality` label were needed (a list endpoint's list record is
already persisted as `live_full_payload`, the richest available payload).

### Status taxonomy

Each selected project/endpoint is classified into exactly one status:

| Status | Meaning | Run effect |
| --- | --- | --- |
| `ok_payload_landed` | live success, retrieved > 0, current live rows present | green |
| `ok_empty_result` | live success, retrieved == 0 (valid no-data / no-tool stage) | green |
| `ok_skipped_with_reason` | skipped (ineligible / unsupported / 403 / 404 / company-level already handled) — reason always recorded | green |
| `degraded_raw_payload_landing_missing` | retrieved > 0 but no current live rows | fails the gate (replay blocked) |
| `degraded_detail_payload_unavailable` | detail/full endpoint returned a list but the richer payload did not land | fails the gate |
| `degraded_external_blocked` | transport / contract / normalizer failure — never green; run already degraded by the procore stage | does not block replay over landed rows |
| `blocked_unsafe_mapping` / `blocked_unknown_allowlist_key` | unsafe mapping / unknown allowlist key | run blocked before live reads |

Valid empty/no-tool endpoints (`ok_empty_result` / `ok_skipped_with_reason`) never degrade
the run. A retrieval that genuinely did not land stays fail-closed
(`degraded_raw_payload_landing_missing`). Transport failures are classified
`degraded_external_blocked` — explicitly non-green — but do not block replaying the
payloads that did land. Company-level endpoints (e.g. `projects`) are fetched once and
their per-project duplicates are recorded as `ok_skipped_with_reason`; landing is attributed
to the concrete `project_key` the endpoint ran under.

The detail-vs-list distinction comes from the canonical `EndpointAdapter`
(`_endpoint_requires_detail_payload`: `parent_path_template` set and `pagination == "none"`).
The entire current daily-refresh plan is list-only (`meeting-detail` is the only detail
endpoint and is not in the plan), so `degraded_detail_payload_unavailable` is kept for
forward coverage.

### Source-quality precedence

Projection replay selects `raw_procore_payload_persisted=1 AND is_current=1` regardless of
quality and applies the per-record `SOURCE_QUALITY_RANK` guard
(`live_full_payload` > `fixture_full_payload` > `redacted_legacy_projection`) so a fresh
live row is never overwritten by a stale/lower-quality one. The freshness gate counts
`live_full_payload` only; a production live run is therefore satisfied by live source-quality
rows exclusively — `fixture_full_payload` counts only in tests / explicit mock-local mode.

### Receipt — `raw_full_payload_freshness`

Metadata only (no payload values): `ok`, `status`, `counts_by_status` (the eight statuses
above), `external_blocked_count`, `missing_fresh_raw_payload_count` (landing + detail
failures), `missing_fresh_raw_payloads[]` (project/endpoint/retrieved/landed + reason),
`raw_rows_by_project`, `raw_rows_by_project_endpoint`, `classified_endpoints[]`,
`sync_run_ids_checked` (transparency only — not a gate input), and `guardrails`.

### Known limitations

- `capture_run_id` is not refreshed on idempotent re-run upserts; the gate intentionally
  does not depend on it. Tightening "this-run confirmation" would use `payload_seen_last_utc`
  against a run-start threshold (not implemented — presence is sufficient for replay).
- Changed payloads create a new `is_current=1` row without retiring the prior one, so a
  record can have more than one current row. This pre-existing data-quality nuance inflates
  `raw_rows_by_*` counts above retrieved counts; it does not affect the presence gate.
