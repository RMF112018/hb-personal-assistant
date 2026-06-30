# Phase 1 Summary - Canonical Package Merge

## Objective

Implement canonical XER/XML package merge for `TWNU18.zip` and `TWNU19.zip`.

## Base commit

`e5187c85` — `fix(schedule): close sqlite connections in schedule read paths`

## Fresh-agent audit

Independent verification: `fresh-agent-audit-20260630T130846Z/`

## What changed

- Canonical current activity merge uses activity ID across equivalent XER/XML current schedules.
- Current relationship merge normalizes P6 relationship type aliases and deduplicates by schedule-scoped identity.
- Equivalent complete XER/XML code and UDF collections no longer double analytical rows.
- Activity raw merge data includes inspectable merged source files, source object IDs, field lineage, and field conflicts.
- `ScheduleActivityRepository.get_activity_merge_lineage()` exposes lineage/conflict data.
- Exact same ZIP package re-import is idempotent: prior committed import is superseded; one active canonical subgraph remains.
- Real TWNU ZIP fixtures under `tests/fixtures/project_schedule_import_packages/`.
- Isolated proof script: `scripts/prove_schedule_canonical_package_merge.py`.

## Files changed (3 core source + tests/proof)

- `src/hb_assistant/construction/analytics/schedule_package_assembly.py`
- `src/hb_assistant/construction/analytics/schedule_import_service.py`
- `src/hb_assistant/store/schedule_activity_repository.py`
- `tests/test_schedule_import_health_foundation.py`
- `tests/schedule_project_test_helpers.py` (`clear_schedule_cpm_runs`)
- 6 CPM test files (isolation-only edits; audit verified no algorithm assertion removal)
- `scripts/prove_schedule_canonical_package_merge.py`
- `tests/fixtures/project_schedule_import_packages/TWNU18.zip`, `TWNU19.zip`

## Tests run (fresh-agent 2026-06-30)

| Gate | Result | Evidence |
|------|--------|----------|
| Focused pytest (43) | **PASS** | `fresh-agent-audit-20260630T130846Z/pytest-focused-before-fixes.txt` |
| `pytest -k "schedule and import"` | **PASS** (1 skip) | `fresh-agent-audit-20260630T130846Z/pytest-schedule-import-before-fixes.txt` |
| `.venv/bin/python -m py_compile` | **PASS** | `fresh-agent-audit-20260630T130846Z/py-compile-before-fixes.txt` |
| `scripts/test-schedule.sh` | **323 passed**, 2 deselected | `fresh-agent-audit-20260630T130846Z/scripts-test-schedule-before-fixes.txt` |

**Note:** Prior `phase1-summary.md` claim of 10 `scripts/test-schedule.sh` failures was **stale/incorrect**. Fresh run passes fully.

## Proven behavior (fresh-agent proof script)

| Package | Activities | Relationships | Codes | UDFs | Baselines |
|---------|-----------|---------------|-------|------|-----------|
| TWNU18 | 1,378 | 3,718 | 5,171 | 4,311 | 2 (1177/2658, 1420/3780) |
| TWNU19 | 1,507 | 3,921 | 5,171 | 4,311 | 2 (1177/2658, 1378/3718) |

- Duplicate buckets: all zero after double import
- CPM `computed_activity_count` matches canonical activities (1378 / 1507)
- Lineage probe shows XER + XML source files
- `equivalence_status: compatible`

Proof output: `fresh-agent-audit-20260630T130846Z/prove-schedule-canonical-package-merge.txt`

## Commit status

Phase 1 is committed.

- Commit: `3a84aab2f63e7beb903feff785fd747457c7a3cd`
- Message: `fix(schedule): merge equivalent schedule package files canonically`
- Final evidence: `fresh-agent-audit-20260630T130846Z/*-final.txt`

## Remaining gaps (deferred)

- `as_of` propagation hardening
- CPM observability schema (Phase 2)
- Frontend import UX
- HTML package support
- Review workbench alignment
- Migration/backfill for historical duplicate rows

## Recommended next step

Use this Phase 1 commit as the base for Phase 2 CPM observability and final merge-readiness validation.
