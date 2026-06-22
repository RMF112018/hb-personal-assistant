# Schedule XER quality metric repair

**UTC:** 20260622T162600Z  
**Branch:** `feature/schedule-project-association-ui` (PR #93)

## Problem

Live TWNU18 XER scorecard showed misleading metrics:

- `dcma_invalid_dates` displayed `1410/1378` (numerator > denominator)
- `dcma_high_duration` treated XER hours as days (533 false failures)
- `dcma_critical_path_test` showed `0/32` without explaining 269 export driving-path flags
- GAO coding coverage reported `0` despite 5171 code assignment rows in DB

## Fixes

1. **XER parser** — map `actual_start`/`actual_finish` from XER task dates; set `duration_unit=hour`
2. **Invalid dates metric** — subcategory buckets with per-basis denominators; `numerator <= denominator` invariant
3. **High duration** — hour→day normalization for `primavera_xer` via `source_format`
4. **Critical path proxy** — enriched evidence (`eligible` vs `export flags`, `cpm_recalculation: not_implemented`)
5. **Code/UDF coverage** — load assignment tables in quality data loader; surface in GAO/DCMA evidence
6. **UI** — `formatMetricValue()` shows findings count, proxy labels, FS distribution (no impossible ratios)

## Validation

```bash
pytest tests/test_schedule_xer_quality_metrics.py tests/test_schedule_critical_path_quality.py tests/test_schedule_quality_engine.py
pytest tests/test_schedule_*.py tests/test_schedule_project_association.py -m "not integration and not live and not manual"
cd frontend && npm test -- ScheduleQualityPage && npm run build
```

Logs: `backend_tests.log`, `frontend_tests.log`

## Live re-import note

Parser field repairs apply on **new commits**. Operator must supersede re-import TWNU18.xer and rerun quality evaluation on `tropical|1069|2026-05-26 08:00` for live proof.

## Expected post-rerun signals

| Metric | Before | After (expected) |
|--------|--------|------------------|
| invalid_dates UI | `1410/1378` | `N findings` with completed-activity basis |
| high_duration | 533/1378 | sharply lower (hours normalized) |
| critical_path | `0/32` only | `0 violations / 32 eligible` + `269 XER flags` |
| GAO coding | `activity_code_coverage_count: 0` | distinct activity count from assignments |