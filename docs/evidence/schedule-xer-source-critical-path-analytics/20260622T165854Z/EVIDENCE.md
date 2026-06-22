# XER source critical path analytics

**UTC:** 20260622T165854Z

## Change summary

Introduced first-class `source_critical_path_available` (`metric_family=source_export`) distinct from:

- `dcma_critical_path_test` (still `not_measurable_requires_recalculation`)
- `source_driving_path_integrity_proxy` (supplemental advisory only)

XER classification branches on `PROJECT.critical_path_type`:

- `CT_DrivPath` → basis `xer_driving_path_flag`
- `CT_TotFloat` → basis `xer_total_float_threshold` (<= `critical_drtn_hr_cnt`)

## Live proof (quality rerun)

See `live_quality_proof.json` and `live_db_proof.txt`.

| Version | Expected basis | Key counts |
|---------|----------------|------------|
| PGA (`pga-modern-garage|61340|2025-12-15 08:00`) | `xer_driving_path_flag` | 150 driving / 1081 explicit float |
| TWNU (`tropical|1069|2026-05-26 08:00`) | `xer_total_float_threshold` | 664 critical-by-float / 269 driving / 32 driving+float |

Downstream readiness: `critical_path_analytics = available_source_export_critical_path`.

## Validation

| Check | Result |
|-------|--------|
| Backend critical-path tests | pass (`backend_tests.log`) |
| Frontend schedule tests | pass (`frontend_tests.log`) |
| `npm run build` | pass (`frontend_build.log`) |

## Hygiene

No secrets in evidence artifacts (`hygiene_summary.json`).