# Test Results Summary

Interpreter: `.venv/bin/python3.12` (3.12.11 — the real toolchain; bare `python` is an empty 3.14).
Command: `pytest tests -m "not integration and not live and not manual"`

## Feature tests (all pass)

- tests/test_phase_10_email_followup_schema.py
- tests/test_phase_10_raw_followup_window.py
- tests/test_phase_10_email_followup_route.py
- tests/test_phase_10_email_followup_engine.py
- tests/test_phase_10_email_followup_cli.py
- tests/test_phase_10_email_followup_daily_brief.py
- Schema/lifecycle regression: test_phase_10_schema, test_data_quality_table_inventory, and the
  V26–V38 lifecycle-classification tests (contract_table_count 221 → 222) — pass.

## Broad suite (regression isolation via clean-main worktree at d7c13a88, same interpreter)

- Clean main baseline: 
- This branch: 
- Failures unique to this branch: **9** — all `test_launcher_scheduler.py` (7) +
  `test_fastapi_analytics_*` (2). Proven to be caused by the untracked, foreign
  `config/config.yml` (live-read flags polluting `resolve_profile('production')`), NOT by this
  feature: copying `config/config.yml` into the clean-main worktree reproduces the same failures on
  clean code. `config/config.yml` is left untouched (foreign/local).
- All other branch failures also fail on clean `main` (Phase 09 retrieval/vector/semantic SDK
  gates, data-quality / no-writeback proofs, repo sensitive-scan's two non-feature findings,
  email_task_extraction, email_body_indexing, etc.). They are pre-existing and unrelated.

## Conclusion

This feature introduces **zero test regressions**. Changed source/test files are clean under
`ruff check` and `mypy` (per-file scope).
