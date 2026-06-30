# Schedule FD Hardening — Final Validation

**UTC timestamp:** 20260630T084500  
**Base:** `origin/main` @ `45177794` (Phase 8C merged)  
**Branch:** `fix/schedule-fd-hardening-20260630T083255`

## Pre-patch (baseline failure)

- `test_schedule_repository_paths_do_not_leak_fds` — FAILED (FD growth 17→243+)
- `test_schedule_suite_paths_succeed_under_constrained_fd_budget` — FAILED (`sqlite3.OperationalError: unable to open database file`)

See `fd-hardening-baseline-failure.txt`.

## Patch applied

### Pattern A — `_conn()` context managers (8 files)

- `schedule_activity_repository.py`
- `schedule_import_repository.py`
- `schedule_mapping_repository.py`
- `schedule_quality_repository.py` (read paths)
- `schedule_cpm_repository.py`
- `schedule_identity_repository.py`
- `project_schedule_hub_repository.py`
- `schedule_project_catalog.py`

### Pattern B — quality write paths

- `schedule_quality_repository.py`: `enqueue_evaluation`, `claim_pending_run`, `complete_run`, `fail_run`, `insert_metric_results`, `insert_scorecard`, `insert_findings`

### Additional fix (required for FD test green)

- `migrator.py` `current_version()` — use `open_connection` (leaked FD on every `ensure_schedule_schema` call via quality service reads)

## Validation

| Gate | Result |
|------|--------|
| `py_compile` on changed files | PASS |
| `tests/test_schedule_fd_hardening.py` | **PASS** (2/2) |
| Focused schedule regression | **81 passed, 1 skipped, 3 failed (pre-existing)** |

### Focused regression failures (pre-existing on `origin/main`)

- `test_twnu_quality_scorecard_when_zip_present[TWNU07.xml]`
- `test_twnu_quality_scorecard_when_zip_present[TWNU16.xml]`
- `test_twnu_quality_scorecard_when_zip_present[TWNU18.xml]`

Assertion: expected `not_measurable_missing_data`, got `not_measurable_requires_recalculation`. Verified failing without FD patch (stash revert). Not introduced by this change.

## Branches explicitly NOT merged

- `feature/schedule-test-fd-hygiene` (test file only copied)
- `feature/forecast-ui-live-config-promotion-orphan-fix`
- `safety/frontend-errorcopy-wrong-base-20260622T140716Z`
- `feature/v65-schema-quality-repair`
- `fix/schedule-import-health-foundation-20260626`
