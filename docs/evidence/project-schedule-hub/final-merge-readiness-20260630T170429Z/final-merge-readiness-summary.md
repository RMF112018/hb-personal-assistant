# Final Merge Readiness - Schedule Canonical Merge + CPM Import Observability

## Branch

`feature/schedule-canonical-package-merge-20260630T093009Z`

## Reviewed implementation commits

- `3a84aab2f63e7beb903feff785fd747457c7a3cd` `fix(schedule): merge equivalent schedule package files canonically`
- `a787d70970b994d2698cff7e6e0c30cde409434d` `fix(schedule): audit cpm recompute after canonical imports`

## Evidence closeout commit

- `f4b88678` `docs(schedule): close out canonical import evidence`

## Main reconciliation commit

- `1c5464594cbc6aa1054c9546fec2c31fe0c0ba02` `merge: reconcile schedule canonical import branch with main`

## Final validation after origin/main reconciliation

- Focused schedule import/API tests: PASS, 43 tests (`pytest-focused-final-after-main.txt`)
- Selected schedule/import/CPM tests: PASS, 23 tests (`pytest-selected-final-after-main.txt`)
- `py_compile`: PASS (`py-compile-final-after-main.txt`)
- `scripts/test-schedule.sh`: PASS, 323 passed, 2 deselected, 1 warning (`scripts-test-schedule-final-after-main.txt`)

## Confirmed behavior

- TWNU18 canonical package merge: 1 current schedule/version, 1,378 current activities, 3,718 relationships, 5,171 code assignments, 4,311 UDF values, 2 linked XML baselines.
- TWNU19 canonical package merge: 1 current schedule/version, 1,507 current activities, 3,921 relationships, 5,171 code assignments, 4,311 UDF values, 2 linked XML baselines.
- Baselines remain separate from current schedule counts; XML `<BaselineProject>` records do not inflate current activities or relationships.
- Lineage/conflict proof is exposed through `ScheduleActivityRepository.get_activity_merge_lineage()` and recorded in Phase 1 evidence.
- Idempotency proof covers same-ZIP re-import without duplicate current schedule/activity/relationship/code/UDF rows.
- CPM proof covers canonical input counts, success status, durable failure status, retry against the same canonical schedule version, and unchanged canonical rows across retry.

## Final git status at summary creation

Only final closeout evidence files were untracked before the final evidence commit:

```text
?? docs/evidence/project-schedule-hub/final-merge-readiness-20260630T170429Z/main-reconcile.txt
?? docs/evidence/project-schedule-hub/final-merge-readiness-20260630T170429Z/py-compile-final-after-main.txt
?? docs/evidence/project-schedule-hub/final-merge-readiness-20260630T170429Z/pytest-focused-final-after-main.txt
?? docs/evidence/project-schedule-hub/final-merge-readiness-20260630T170429Z/pytest-selected-final-after-main.txt
?? docs/evidence/project-schedule-hub/final-merge-readiness-20260630T170429Z/scripts-test-schedule-final-after-main.txt
```
