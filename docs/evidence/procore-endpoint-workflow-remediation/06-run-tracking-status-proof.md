# 06 — Run Tracking & Operator Status Proof

Prompt: `06_RUN_TRACKING_AND_STATUS_SURFACES.md`.

## Run-tracking decision

- **`procore_sync_runs` is retired**, not revived. DB proof: `procore_sync_runs = 0` and `procore_sync_errors = 0` — the legacy coordinator's `upsert_procore_sync_run`/`upsert_procore_sync_error` were never called by the scheduler path. Rather than wiring an inert ledger, the daily refresh now uses the canonical ledger.
- **`procore_live_sync_runs` is the canonical endpoint run ledger.** `run_live_sync` records a start row (`record_sync_run_start`) and a completion row (`record_sync_run_complete`) with `status`/`state`/`reason_codes`/counts for every applied endpoint. DB proof: 508 rows with a real status/state taxonomy (`success`/`partial`/`error` × `success`/`partial_success`/`transport_error`/`in_progress`).
- **`assistant_runs` remains the global scheduler run ledger** (recorded by `scheduler/daily_source_refresh.py`), not a substitute for endpoint-level Procore history.
- Status surfaces no longer imply `procore_sync_runs` should advance: the new `procore live status` labels it `"legacy run ledger — retired (never written by the scheduler path)"`.

## Status surface (new `hb-assistant procore live status`)

Read-only over local SQLite; safe fields only. Shows:

- **Live gate**: `hb_procore_live_armed` (HB_PROCORE_LIVE) + `auth_status` + `ready_for_live_calls`.
- **Canonical path**: `procore_live` + `canonical_tables` + `canonical_counts`.
- **Legacy path**: `procore_sync` + `legacy_counts` + retirement note.
- **`table_roles`**: human-readable role for each canonical/legacy table.
- **Per-pilot freshness** (`build_freshness_report`): current/stale/never/fail_closed counts + stale endpoints.
- **`next_operator_action`** + **`inspect_hint`** (safe inspection commands).

### Captured example (production, safe fields)

```json
{
  "canonical_counts": {"procore_live_records": 30035, "procore_live_sync_runs": 508, "procore_live_sync_watermarks": 160},
  "legacy_counts": {"procore_synced_entities": 1185, "procore_sync_watermarks": 12, "procore_sync_runs": 0, "procore_sync_errors": 0},
  "live_gate": {"hb_procore_live_armed": false, "auth_status": "env_present", "ready_for_live_calls": true},
  "pilot_projects": ["tropical", "pga-modern-garage", "alton-hilltop-pbg", "the-wellington"]
}
```

The scheduler receipt + `scheduler status` continue to surface scheduler run
status, `last_status`, redacted `db_path`/`evidence_path`, `last_receipt_path`,
`live_reads_enabled`, and `last_run.next_operator_action`. The Procore stage
summary inside the persisted orchestrator summary now adds `endpoint_summary`,
`by_status`, `tables_written`, and the Procore-specific `next_operator_action`
(Phase C).

## Exit-code behavior (unchanged, intentional)

- Manual degraded run → exit **2** (`tests/test_scheduler_degraded_surfacing.py::test_manual_degraded_run_exits_2`).
- Manual clean run → exit **0**.
- Scheduled ticks retain their unattended behavior.

## Tests

Run-ledger insert/update, degraded tracking, status safe-fields, and no-leak
tests are added in Phase F (`08-tests-and-guardrails.md`); the canonical ledger
writes are already covered by the `test_procore_live_sync_*` /
`test_procore_repositories_v6` suites.
