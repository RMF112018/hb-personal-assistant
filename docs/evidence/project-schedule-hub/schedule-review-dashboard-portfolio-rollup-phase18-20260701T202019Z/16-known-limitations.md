# Known limitations

- Portfolio dashboard uses a **per-project loop** over thin trust slices. Acceptable for current project counts; pagination/batching recommended if catalog grows beyond ~50 projects.
- **Preview cue counts** include quality preview cues only (not full driver/milestone workbench preview sync). Persisted review items are fully counted from the review repository.
- **Placeholder portfolio APIs** (`/api/projects/portfolio`, `/api/projects/all/overview`) remain unchanged; schedule intelligence is on `/api/projects/schedule-review-dashboard`.
- **Fixture vs live evidence:** artifacts `03`–`14` and screenshots `09`–`14` use a seeded fixture DB (`fixture-phase18-portfolio.db`). They prove API shape, redaction, and UI wiring—not production data. Live DB proof is artifacts `18`–`26` from `capture_phase18_live_smoke.py` (GET-only; mutation attestation in `26-live-smoke-notes.md`).
- **Named-baseline regression tests** (pre-existing on `main` at `19d37316`; not introduced by Phase 18):
  - `tests/test_project_schedule_named_baseline_comparison_accuracy.py::test_prior_update_disposition_does_not_join_named_workbench` — fails with `assert open_prior` (`open_prior == []`).
  - `tests/test_project_schedule_multi_baseline_controls.py::test_controls_named_includes_workbench_links` — fails with `pytest.fail("expected at least one activity-backed control")`.
  - Verified 2026-07-01 by checking out `19d37316` in the main repo and running both tests with `python -m pytest … -q` (2 failed).
- Rollup depends on imported schedule data and operator review workflows; no automatic dispositions.
- HTML-in-ZIP schedule imports remain unsupported.
