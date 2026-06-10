# Known Limitations — Phase 10 Full Candidate Implementation

## Scope / posture
- The codebase was already mature, so each candidate is a **surgical convergence/hardening slice +
  evidence** rather than greenfield. New surfaces are additive, read-only/dry-run report-style
  commands and one status-file enrichment. No schema changes; no new product scope.

## Pre-existing, unrelated test failures (NOT caused by this branch)
Confirmed pre-existing by stash-testing (they fail with this branch's changes removed); they live in
subsystems none of the candidates touched, and depend on the real (Dev) app DB / environment:
- `tests/test_phase_09_review_burden_cli.py::test_review_burden_and_queue_and_clusters_smoke`
  (`unable to open database file`).
- `tests/test_launcher_scheduler.py::*` (several; launcher/scheduler subsystem + real DB).
- `tests/test_phase_08b_data_quality_gates.py::test_statuses_pass_and_defer_no_fail`.
- `tests/test_fastapi_analytics_source_refresh_surfaces.py::test_live_refresh_fails_closed`.
- `tests/test_phase_10_email_task_extraction.py::test_commitment_persists_to_commitment_table`.
See each candidate's `validation-results.md` for the stash-test confirmation.

## Pre-existing lint (NOT this branch)
- `ruff check src/hb_assistant/cli/procore.py` reports 3 pre-existing `B008` (lines 696/1088/1889) in
  code not added by Prompt 06; every option added by the new `monitor` verb carries `# noqa: B008`.

## Concurrent repo-mutation hazard (environmental)
- Throughout the run, background processes (data-quality / automation / financial / graph-proof
  dry-runs) intermittently regenerated OTHER phases' evidence files on the working tree. These were
  never staged (every commit used explicit-path `git add`) and were restored to baseline. This is the
  documented `hb-concurrent-repo-mutation-hazard`; it did not affect any candidate's committed work.

## Deferred / not implemented (intentional)
- No model-assisted grouping in the report candidates (02/03/05/07/09) — deterministic by design.
- Document parsing uses synthetic fixtures only (no live document corpus, per the prompt + safety).
- No new promotion/apply path in the relationship candidate (the existing
  `relationship-candidates scan --apply` remains the bounded apply).
- macOS next-active-machine semantics for the scheduler are launchd-native (a missed weekday
  `StartCalendarInterval` fires on next wake); not independently re-implemented.
