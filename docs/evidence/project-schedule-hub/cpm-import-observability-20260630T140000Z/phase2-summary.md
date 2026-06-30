# Phase 2 — CPM import observability

## Objective

Make post-import CPM recompute auditable against canonical current data with durable status, diagnostics, failure visibility, and retry idempotency.

## Implementation

- **V95 migration** — `schedule_cpm_import_observability` table (one row per `import_id`, upsert on retry)
- **Repository** — `ScheduleCpmImportObservabilityRepository` with canonical input counts and durable upsert
- **Recompute service** — `ScheduleCpmRecomputeService.recompute()` accepts `import_id`, `package_id`, `trigger_source`; persists observability on success and failure
- **Import commit** — passes import context into recompute; exposes `cpm_observability` and canonical/graph counts in commit payload
- **Pipeline** — `build_status` / `retry_cpm` merge observability into public CPM fields; failed status surfaces on status endpoint

## Tests (9 required + migration)

All in `tests/test_schedule_cpm_import_observability.py`:

1. `test_import_commit_triggers_cpm_after_canonical_merge_twNU18`
2. `test_import_commit_triggers_cpm_after_canonical_merge_twNU19`
3. `test_cpm_input_counts_match_canonical_counts`
4. `test_import_status_exposes_cpm_success`
5. `test_import_status_exposes_cpm_failure`
6. `test_failed_cpm_run_is_durable`
7. `test_cpm_retry_uses_same_canonical_schedule_version`
8. `test_cpm_retry_does_not_duplicate_canonical_records`
9. `test_reimport_does_not_duplicate_canonical_records_or_hide_cpm_status`

Plus `tests/test_migrator_v95_cpm_import_observability.py`.

## Validation (all PASS)

| Gate | Result | Evidence |
|------|--------|----------|
| `pytest tests/test_schedule_cpm_import_observability.py` | 14 passed | `pytest-cpm-observability.txt` |
| Phase 2 bundle (health + pipeline + hub API) | 43 passed | `pytest-phase2-bundle.txt` |
| `pytest -k "schedule and import and cpm"` | 23 passed | `pytest-selected-schedule-import-cpm.txt` |
| `py_compile` | PASS | `py-compile.txt` |
| `scripts/test-schedule.sh` | 323 passed, 2 deselected | `scripts-test-schedule.txt` |

## Commit

Message: `fix(schedule): audit cpm recompute after canonical imports`
