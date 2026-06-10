# Validation Results

- Targeted pytest: passed, `22` tests:
  - `tests/test_procore_structured_analytics_foundation.py`
  - V46 lifecycle-contract count/classification subset.
  - V45 email-followup schema compatibility subset.
- Ruff on touched package files passed with `--extend-ignore B008` for the existing Typer option
  defaults in `src/hb_assistant/cli/procore.py`.
- Mypy on `structured_analytics.py`: passed.
- Copied DB migration/backfill validation: passed.
- Production DB unchanged proof: before/after hash matched.
- Full `pytest tests -q` was run after the V46 lifecycle classification fix and reported `24`
  failures. Two were stale contract-count assertions caused by the intentional V46 table-count
  increase from `222` to `269`; those two were fixed and the targeted inventory tests passed. The
  remaining broad failures are outside the Procore structured analytics package:
  - automation executor proof/gate failures.
  - raw-content calendar/email body indexing expectations.
  - email-module forbidden-token scan against existing `graph.py`.
  - missing worktree-local `.venv/bin/hb-assistant` in one subprocess test.
  - review-burden CLI DB path failure.
  - email task extraction persistence expectation.
  - Procore live-inspect auth-vs-output-dir ordering expectation.
  - repo sensitive-scan findings in existing test/frontend files.
  - retrieval embedding fallback vector dimension expectation.
  - second-brain no-writeback proof failures.
- Full `ruff check src tests` was run and failed on existing repo style findings, including legacy
  `B008` Typer defaults in `src/hb_assistant/cli/procore.py`, an unused variable in MCP wrappers,
  and older test style/import issues.
- Full `mypy src` was run and failed on two existing errors in
  `src/hb_assistant/construction/second_brain/review_burden_mart.py`.

Residual note: package-owned V46 validation is green. The broad suite is not green due to the
non-package residuals above.
