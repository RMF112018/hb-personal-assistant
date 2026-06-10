# Validation Matrix — Scheduler / Daily-Run Reliability (Prompt 04)

| Area | Command / Method | Expected | Actual | Status |
|---|---|---|---|---|
| Compile | `compileall daily_run.py` | pass | COMPILE_OK | ✅ |
| New regression | `pytest tests/test_phase_10_daily_run_reliability.py` | pass | 3 passed | ✅ |
| Daily-run/email/launchd suites | targeted pytest | pass | all green | ✅ |
| Lint | `ruff check daily_run.py` | pass | All checks passed | ✅ |
| Types | `mypy daily_run.py` | pass | no issues | ✅ |
| Scheduler install preview | `preview_install()` | dry-run, no write, plist+readiness | `01`/`02`/`08` | ✅ |
| Success status | seeded apply run | result=success, pointer written | `03` | ✅ |
| Degraded status | bogus profile → route blocked | result=degraded, status=partial | `04` | ✅ |
| Failure status | repo-contained output dir | output_path_inside_repo_refused | `05` | ✅ |
| Last-success preservation | success then degraded | pointer unchanged | `06` (true) | ✅ |
| Stable path / no auto-open | path policy + flags | non-repo, not auto-opened | `07` | ✅ |
| Safety scan | forbidden-pattern scan (Apple DTD boilerplate excluded) | no findings | TOTAL_FINDINGS=0 | ✅ |
| Production DB checksum | sha256 before/after | unchanged | UNCHANGED=True | ✅ |
| DB migration | N/A | — | no schema change | ✅ N/A |

## Pre-existing failures (not this candidate)

`tests/test_launcher_scheduler.py::*` and `tests/test_phase_08b_data_quality_gates.py::test_statuses_pass_and_defer_no_fail`
fail in this environment (the `launcher/scheduler` subsystem + data-quality gates depend on the real
(Dev) app DB). Confirmed pre-existing: they fail identically with this candidate's `daily_run.py`
change stashed. This candidate did not touch those modules. Recorded, not fixed.

## Notes

- The launchd `.plist` preview legitimately contains absolute paths (launchd requires them); the
  committed evidence redacts the home dir to `~`. The Apple plist DTD boilerplate URL is excluded
  from the forbidden scan (standard in every XML plist).
- All runs used disposable temp DBs + temp output dirs; production read once, never written.
