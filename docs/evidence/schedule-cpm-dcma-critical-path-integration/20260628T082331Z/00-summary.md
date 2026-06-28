# Schedule CPM DCMA Critical Path Metric Integration — Phase 7

Generated: 20260628T082331Z (UTC)
Branch: feat/schedule-cpm-dcma-critical-path-integration
Base commit: 39fed676 (Phase 6 `feat/schedule-cpm-criticality-foundation`, committed + pushed, NOT on origin/main → branched from the Phase 6 commit; stacked P1→…→7)
Schema: v88 → **v89** (additive status-CHECK widening; NO new tables; table_count unchanged at **477**)

## Implemented
Backend-only integration of the application-computed CPM chain (Phases 1–6) into the EXISTING DCMA critical-path quality metric:
- `construction/analytics/schedule_cpm_dcma_integration.py` (new) — pure, READ-only: `evaluate_dcma_critical_path_eligibility` (dependency + path-integrity + criticality-consistency checks).
- `construction/analytics/schedule_cpm_service.py` — `evaluate_dcma_critical_path(svk)` (READ-ONLY: reads latest CPM runs; returns None when none attempted; never recomputes/writes).
- `construction/analytics/schedule_quality_engine.py` — new measured status `available_app_cpm_recalculated`; `EvaluationContext.computed_cpm_critical_path`; loader populates it (lazy); `_metric_critical_path_test` top branch.
- `construction/analytics/schedule_quality_posture.py` — `classify_critical_path_readiness` additive branch (computed CPM → available_cpm_recalculated True).
- `store/schedule_cpm_repository.py` — `get_criticality_run`. `store/schedule_float_tables.py` — new status in METRIC_STATUS_CHECK_VALUES. `store/migrator.py` — v89 CHECK-rebuild reconcile (mirrors v71).
- Tests: `tests/test_schedule_cpm_dcma_integration.py` (21), computed-CPM additions to `tests/test_schedule_critical_path_quality.py` (4), `tests/test_migrator_v89_schedule_quality_app_cpm.py` (2 — fresh + pre-v89 upgrade).

## Behavior (proven by sample payloads)
- **Source-only** XER/MSP (no CPM chain) → `not_measurable_requires_recalculation` (unchanged); source-export + supplemental proxy metrics still produced separately.
- **Computed CPM chain present + valid** → `available_app_cpm_recalculated`, basis `application_computed_cpm`, dependency run ids {forward,backward,float,longest_path,criticality}, `source_critical_flags_used:false`. Source-export evidence still separate.
- **Chain incomplete/inconsistent** (attempted) → stays not measurable with the computed-CPM-specific reason codes (e.g. `missing_backward_run`), not the generic source reason.
- **No CPM attempted** (none of the 5 runs) → evaluation is None → existing source-only behavior untouched (distinct from attempted-but-incomplete).

## Explicitly NOT implemented
No frontend/storytelling. No source critical/driving-path/float reinterpretation; `is_critical` never read or mutated. No automatic CPM recomputation inside the quality evaluator (read-only). No new tables. DCMA measurability is conservative — any missing/blocked/inconsistent dependency keeps it not measurable.
