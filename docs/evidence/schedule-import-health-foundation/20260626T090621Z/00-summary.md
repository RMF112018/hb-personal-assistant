# Schedule Import Health Foundation

## Starting Base

- Starting branch/ref: `fix/schedule-import-health-foundation-20260626`
- Base commit: `50b00cab`
- Base source: `origin/main`
- Base proof: `origin/main` contained V74 forecast monthly-matrix changes before this remediation.

## Schema Version

- Latest schema version before changes: `74`
- New migration version selected: `75`
- Collision check: V74 is occupied by `v74_forecast_monthly_matrix`; V75 was unused on the selected base.
- Migration posture: additive only. No existing schedule or forecast table was renamed, dropped, repurposed, or destructively backfilled.

## Implementation Summary

- Added package-aware schedule import metadata for single files and ZIP packages.
- Added hierarchy-aware P6 XML package parsing for `Project` and `BaselineProject`.
- Added separate baseline project/activity/relationship/WBS/code/UDF persistence.
- Added capability rows, baseline crosswalks, baseline health facts, diff fact persistence, and backend health-data read API.
- Preserved existing single-file error codes and existing activity/relationship/quality/diff endpoints.
- Added manual ZIP package proof for `TWN.zip`, `Caretta.zip`, and `BlueLake.zip`; SQLite proof databases were excluded from git.

## Validation Summary

- `bash -n scripts/test-schedule.sh`: passed as part of baseline command sequence.
- `scripts/test-schedule.sh --collect-only`: passed before changes; collected 127/129 tests before adding V75 tests.
- `scripts/test-schedule.sh`: passed after changes, `131 passed, 2 deselected, 1 warning`.
- `ruff check src tests`: not available on PATH in this shell; direct venv Python invocations were rejected by the tool policy.
- Manual ZIP package proof: `TWN.zip`, `Caretta.zip`, and `BlueLake.zip` each previewed and committed with package mode `zip_package`, schema `75`, capability rows, baseline rows, crosswalk rows, and health facts.
