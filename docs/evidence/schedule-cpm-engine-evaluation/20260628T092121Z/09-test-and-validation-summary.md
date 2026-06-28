# 09 — Test and Validation Summary

## Test-DB isolation

Backend validation ran with **`HB_ASSISTANT_DB_PATH` unset** so pytest and
`scripts/test-schedule.sh` use their own per-test fixture DBs. The 3.8 GB evidence DB
(`/tmp/hb-schedule-cpm-evaluation.sqlite`) was **not** used by validation — it is used only for
evidence/API/DCMA sample capture. Confirmed in `artifacts/backend-test-output.txt` header
(`env HB_ASSISTANT_DB_PATH=[<unset>]`).

## Backend — `artifacts/backend-test-output.txt`

Started `2026-06-28T10:23:03Z`, finished `2026-06-28T10:30:25Z`. All green; no failures/errors.

| Target | Result |
| --- | --- |
| `tests/test_schedule_cpm_graph.py` | 12 passed |
| `tests/test_schedule_cpm_forward_pass.py` | 18 passed |
| `tests/test_schedule_cpm_backward_pass.py` | 22 passed |
| `tests/test_schedule_cpm_float.py` | 24 passed |
| `tests/test_schedule_cpm_longest_path.py` | 21 passed |
| `tests/test_schedule_cpm_criticality.py` | 23 passed |
| `tests/test_schedule_cpm_dcma_integration.py` | 21 passed |
| `tests/test_schedule_cpm_api.py` | 10 passed |
| `tests/test_schedule_critical_path_quality.py` | 6 passed, **2 skipped** (external TWNU/PGA fixtures) |
| `tests/test_schedule_import_health_foundation.py` | 13 passed |
| `tests/test_schedule_schema_migration.py` | 5 passed |
| `tests/test_data_quality_table_inventory.py` | 4 passed |
| `tests/test_schedule_import_api.py::test_import_preview_and_commit_xer` | 1 passed |
| `bash scripts/test-schedule.sh` | **314 passed, 2 deselected** (301.40s) |

The 2 skips in `test_schedule_critical_path_quality.py` are external-fixture skips (not failures);
the 2 deselected in the bundle are the standard `integration/manual/live` deselection.

## Frontend — `artifacts/frontend-test-output.txt`

Started `2026-06-28T10:23:12Z`, finished `2026-06-28T10:23:19Z`. All green.

| Step | Result |
| --- | --- |
| `npm run typecheck` (`tsc -b`) | clean |
| `vitest run src/pages/ScheduleCpmPage.test.tsx` | **7 passed** |
| `eslint` on `ScheduleCpmPage.tsx`, `ScheduleCpmPage.test.tsx`, `lib/api.ts`, `app/routes.tsx`, `components/schedule/SchedulePageChrome.tsx` | exit 0 (clean) |

## Unrelated / pre-existing (documented, not fixed)

- Per the prior phase session, the full frontend suite has **3 pre-existing reds** in
  `MyItemsPage`/`TodayPage` (unrelated to CPM) and **8 pre-existing eslint errors** in untouched
  files. These were **not** run/fixed here; the CPM-targeted frontend tests and the 5
  CPM-touched files are clean (above). No CPM-scoped failures occurred.
- The working tree carried unrelated obsidian_mcp WIP throughout (doc 01); it did not affect the
  CPM test results (the CPM API routes were unmodified).

## Conclusion

All Schedule-CPM backend and frontend validations pass. The only non-passes are expected skips
(external fixtures) and deselections (`integration/manual/live`), plus pre-existing unrelated
failures that were not in scope.
