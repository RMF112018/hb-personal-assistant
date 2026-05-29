# Phase 04B — Prompt 09 — Schedule & Daily-Log Enrichment

**Date:** 2026-05-29
**Branch:** main
**Project:** tropical (procore_project_id 2525840, pilot; company 5280)
**Scope:** Schedule intelligence enrichment + complete the daily-log coverage
decision using broader date-window live testing.

## Scope decisions

- **No migration / V7 change.** All target tables exist; schedule version /
  data-date history uses the generic history path. Migration stays **7**;
  endpoint registry stays **27**.
- **No schedule normalizer change.** `project_activity` reads `raw` directly
  (mirrors `project_rfi` / `project_submittal` / `project_punch_item`).
- **Daily-log enrichment stays at the normalizer layer** (`daily_log_live.py` via
  `EntityBuilder`); the three required signals were added there, additively.
- **No raw payload dump, no secrets / signed URLs.** The live probe used `live
  smoke` (counts only — no SQLite writes, no payload persistence).

## Files

### Created
- `src/hb_assistant/store/procore_schedule_projection.py` — `project_activity()`.
- `tests/test_procore_schedule_projection.py` — 5 tests (incl. schedule snapshot history).
- `tests/test_procore_live_date_window.py` — 3 tests (date-window params + zero-record handling).

### Modified
- `src/hb_assistant/procore/normalizers/daily_log_live.py` — added `_num` /
  `_manpower_anomaly` helpers and the three required signals (additive).
- `src/hb_assistant/procore/live_sync.py` — import `project_activity`; guarded
  `activities` dispatch block; `start_date`/`end_date` threaded into the GET params.
- `src/hb_assistant/cli/procore.py` — `--start-date` / `--end-date` options on
  `live sync` and `live smoke`.
- `tests/test_procore_daily_log_live_normalizer.py` — assertions for the three new
  signals.

## Schedule enrichment (`project_activity`)

Record key `tropical|activities||<activity_id>`. All writes idempotent.

| Source | Target |
| --- | --- |
| `schedule_id` | edge `in_schedule` → `tropical|schedules||<schedule_id>` |
| `parent_id` | edge `child_of_activity` → `tropical|activities||<parent_id>` (hierarchy) |
| `assigned_company` (str or dict) | `extract_company_refs` + edge `assigned_company` |
| `resource_data[]` | edge `resource` (metadata: resource_name) |
| `category_data[]` | edge `category` (metadata: name/value) |

**Action signals** (classifications in `reason_codes`; `percent_complete`,
`total_float`, `deadline_variance`, `constraint_type`, float band + variance
class carried as primary-signal metadata):
- `activity_critical` — `is_critical` truthy.
- `activity_zero_float` — `total_float <= 0` (band: zero_or_negative / low ≤5 / ample).
- `activity_deadline_variance` — `deadline_variance < 0` (late / on_time / ahead).
- `activity_constrained` — `constraint_type` present and not `ASAP` (high for hard `MSO`/`MFO`).

**Schedule version / data-date history** is captured by the existing generic
history path (`record_procore_history_for_record`) — verified by a test that runs
two `schedules` syncs with advancing `data_date` and asserts ≥2 snapshots and ≥1
change event. **Percent-complete trend** is derivable from those per-sync
snapshots; no bespoke trend table was added.

## Daily-log signals (normalizer layer, additive)

- `daily_delay_reported` — delay section (alongside existing `delay`).
- `daily_note_review_required` — notes section (always review-required).
- `daily_manpower_anomaly` — manpower section when workers are reported with zero
  hours, or hours with zero workers.

## Date-window capability

`run_live_sync` now accepts `start_date` / `end_date`, assembled into the GET
query params alongside `project_id`. Exposed as `--start-date` / `--end-date` on
`procore live sync` and `procore live smoke`. Offline tests confirm the params are
passed for daily-log endpoints (and omitted when not supplied), plus a zero-record
handling test (empty payload → `state=success`, `retrieved_count=0`, no error).

## Live date-window probe (coverage decision)

Token refreshed (`procore auth refresh` → ok, ~90 min validity; no token value
logged). `HB_PROCORE_LIVE=1 ... live smoke --project tropical --endpoint <id>
--start-date 2024-01-01 --end-date 2026-05-29 --confirm-live-get` (counts only; no
SQLite writes). All calls `state=success`, `reason_codes=[]`,
`normalized_count == retrieved_count` (real payloads normalized cleanly — PII
hashing + enrichment held on real shape).

| Section | Endpoint | With date window (max 100) | Without date window |
| --- | --- | --- | --- |
| Weather | daily-log-weather | 100 (cap hit) | 0 |
| Manpower | daily-log-manpower | 100 (cap hit) | — |
| Notes | daily-log-notes | 100 (cap hit) | 0 |
| Deliveries | daily-log-deliveries | 61 | — |
| Delays | daily-log-delays-review-routed | 0 | — |
| Inspections | daily-log-inspections | 100 (cap hit) | — |
| DCRs | daily-log-dcrs | 100 (cap hit) | — |

First-pass run-id prefixes (max-items 10): weather e001d6cb, manpower dbcd8b75,
notes d44b1a68, deliveries 0df2ffee, delays 8faab842, inspections a217793d, dcrs
b38c50b8.

### Coverage decision

**Daily logs carry substantial real value for Tropical** — the prior "zero
records" finding was an artifact of querying without a date window (Procore
daily-log list endpoints default to a narrow/empty window). The control run
(weather, notes) returned **0 without** a date window and **100+ with** one,
confirming `start_date`/`end_date` is the working filter contract and the unlock.

- **Carry data (enable date-window sync):** weather, manpower, notes, deliveries,
  inspections, DCRs.
- **Empty for this window:** delays (`daily-log-delays-review-routed`) returned 0
  across 2024-01-01 → 2026-05-29 — genuinely no delay logs recorded for Tropical,
  not a contract failure.
- Endpoint-specific enrichment was **already** present at the normalizer layer and
  is now confirmed against real payload shape (clean normalization, no PII leak,
  signals fire). No further per-endpoint enrichment was required beyond the three
  new signals.

`live smoke` (no writes) was used for the probe; populating the second-brain store
is a follow-up `live sync --apply --sqlite-only --start-date … --end-date …`
operator step (normalized/redacted rows only — never raw bodies).

## Validation

- `python -m pytest -q tests/test_procore_schedule_projection.py tests/test_procore_live_date_window.py tests/test_procore_daily_log_live_normalizer.py` → **23 passed**.
- `python -m pytest -q --no-header` → full suite **green** (endpoint count 27, migration version 7 unchanged).
- `ruff check .` → **All checks passed**.
- `mypy .` → **Success: no issues found in 201 source files**.
- `python -m compileall -q src tests` → **OK**.
- `hb-assistant diagnostics scan-sensitive --repo . --json` → **0 findings** in the
  new/edited files.
