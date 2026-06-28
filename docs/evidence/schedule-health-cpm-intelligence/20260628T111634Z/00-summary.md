# 00 — Phase 9A.1 Summary: Schedule Health Computed-CPM Aggregation

## What shipped
A **read-only backend aggregation** that exposes Application-computed CPM evidence to the Schedule
Health surface, via an **additive `computed_cpm_health` key** on the existing
`GET /api/schedules/versions/{key}/health-data` response, plus the matching frontend type. No UI
rendering, no recompute, no schema migration, no source-field mutation, no capability-writer edit.

## Coordinates
- Branch: `feat/schedule-health-cpm-intelligence-9a1` (isolated worktree off `origin/main` @ `37767f36`, schema v89).
- Evidence: `docs/evidence/schedule-health-cpm-intelligence/20260628T111634Z/`.
- **Uncommitted** pending Bobby's authorization.

## Changes
- `src/hb_assistant/store/schedule_cpm_repository.py` — new read-only `float_risk_counts(cpm_run_id, *, high_total_float_days)` (single `GROUP BY` over `schedule_cpm_activity_results`; negative/zero/high/classified total-float buckets).
- `src/hb_assistant/construction/analytics/schedule_health_cpm_service.py` — new `ScheduleHealthCpmService.build_computed_cpm_health(svk)` composing `cpm_summary`/`cpm_longest_path`/`cpm_diagnostics` + run-row aggregates + float buckets into the envelope. Fail-soft `available:false`.
- `src/hb_assistant/construction/analytics/api.py` — `_schedule_health_cpm_service()` factory + fail-soft enrichment of `/health-data`.
- `frontend/src/lib/api.ts` — `ComputedCpmHealth` interface + optional `ScheduleHealthData.computed_cpm_health`.
- `tests/test_schedule_health_cpm_aggregation.py` (+ added to `scripts/test-schedule.sh`).

## Validation (see `test-output.txt`)
- New tests: **6 passed**. Adjacent CPM/quality/import-health tests: no regression.
- Full bundle `scripts/test-schedule.sh`: **320 passed / 2 deselected** (314 + 6).
- ruff: owned files clean; `api.py` 37 pre-existing errors (identical on `origin/main`), 0 added.
- Frontend: typecheck clean, `eslint src/lib/api.ts` clean.
- Real-data smoke (`sample-health-response.json`, schema-89 evidence DB, `tropical|1071|2026-06-23 08:00`):
  `computed_cpm_health.available:true`; 1507 computed activities, 1312 critical, 1 near-critical,
  45 longest-path members; float buckets 1308 neg / 4 zero / 153 high (threshold 44);
  longest path 45 activities / duration 429 / total float −296; DCMA measurable, basis
  `application_computed_cpm`, `source_critical_flags_used:false`, caveat
  `computed_critical_outside_longest_path` carried.

## Provenance (see `metric-provenance-map.md`)
Every envelope value is `application_computed_cpm`; source-export health stays separate and
unchanged. No source critical/driving/float fields surfaced. Caveats never hidden. Longest path is
the computed longest path, not a "true/P6/forensic" critical path.

## SOW corrections (see `repo-truth-audit.md`)
1. Project-scope mismatch on `/health-data` → **404** (not 400; 400 is the commit path).
2. Float-bucket counts were **not** pre-aggregated — added a cheap `GROUP BY`; criticality/
   near-critical/longest-path-member counts were already pre-aggregated (no row hydration).

## Next (later stacked PRs)
9A.2 cockpit layout · 9A.3 CPM Intelligence panel (recharts already available) · 9A.4 quality
drilldowns · 9A.5 baseline/source · 9A.6 risk visualizations · 9A.7 export-readiness · 9A.8 closeout.
The UI-facing evidence (`smartpm-benchmark.md`, `frontend-surfacing.md`, `sample-ui-state-notes.md`)
lands with those phases.
