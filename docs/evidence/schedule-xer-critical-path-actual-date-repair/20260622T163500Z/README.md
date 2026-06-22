# XER critical path and actual date repair

**UTC:** 20260622T163500Z  
**Branch:** `feature/schedule-project-association-ui` (PR #93)

## Problems fixed

1. **DCMA critical path test** — XER driving-path proxy no longer masquerades as measured `dcma_critical_path_test`; status is `not_measurable_requires_recalculation`.
2. **Supplemental proxy** — `source_driving_path_integrity_proxy` (`metric_family: supplemental`) reports export driving-path integrity separately.
3. **Actual dates** — Parser maps `actual_start`/`actual_finish` from `act_start_date`/`act_end_date` only; invalid-dates checks use canonical fields (no `finish_date` fallback).

## Live after rerun (pre re-import)

**Version:** `tropical|1069|2026-05-26 08:00`

| Metric | Status | Notes |
|--------|--------|-------|
| `dcma_critical_path_test` | `not_measurable_requires_recalculation` | DCMA 14-point slot correctly not measurable |
| `source_driving_path_integrity_proxy` | `measured_from_source_export_proxy` | `0/32` eligible; 269 driving-path flags |
| `dcma_invalid_dates` | `failed_threshold` | `actual_finish_after_data_date` findings **0**; 705 completed missing actual finish; 733 started missing actual start |

**DCMA measured / not measurable:** 9 / 5 (was 10 / 4)

**Score / grade:** 71.4 / C (proxy no longer counts as DCMA pass)

## Parser re-import required

Strict `act_*` mapping applies on **new commits**. Operator must supersede re-import `TWNU18.xer` to populate canonical actual fields from raw XER.

## Validation

```bash
pytest tests/test_schedule_xer_quality_metrics.py tests/test_schedule_critical_path_quality.py tests/test_schedule_quality_engine.py tests/test_migrator_v70_schedule_quality_supplemental.py
pytest tests/test_schedule_*.py tests/test_schedule_project_association.py -m "not integration and not live and not manual"
cd frontend && npm test -- ScheduleQualityPage && npm run build
```

Logs: `backend_tests.log`, `frontend_tests.log`, `live_after_metrics.sql.out`