# Procore Endpoint Structured Analytics Foundation Evidence

Manifest: `Procore Endpoint Structured Analytics Foundation + Daily-Brief Usefulness Package`
version `v2.0.0-structured-analytics-foundation`.

This evidence is scrubbed and contains no raw Procore payloads or DB extracts. Private DB validation
used `/tmp/hb-procore-structured-analytics-foundation-audit-20260610-054842/`.

Key proof points:

- Unique worktree branch: `feature/procore-structured-analytics-foundation`.
- Base/main/origin main: `dbff6e89b21885dab7b5db32186671ff8fda44f9`.
- Production DB backup used SQLite `.backup`.
- Backup integrity check: `ok`.
- Backup quick check: `ok`.
- Copied DB migrated from schema `45` to schema `46`.
- Full copied-DB legacy reprocess inspected `30,059` local Procore live records.
- Raw landing rows written on copied DB: `30,059`.
- Structured endpoint-family rows written on copied DB: `30,059`.
- Live Procore calls during reprocess: `0`.
- External writeback during reprocess: `0`.
- Production DB hash before/after validation: `f93b78081dfbbd7d40ebbfc9254227eab7d306bb08d73e8b92d76e7b33ae4759`.

Validation summary:

- `pytest tests/test_procore_structured_analytics_foundation.py -q`: passed, `8` tests.
- V46 lifecycle/table-inventory/V45 compatibility subset: passed, `14` tests.
- `ruff check` on new module, migrator, and new tests: passed.
- `ruff check --extend-ignore B008 src/hb_assistant/cli/procore.py`: passed; the ignore is needed for existing Typer option defaults in that file.
- `mypy src/hb_assistant/procore/structured_analytics.py`: passed.
- Full `pytest tests -q`: run; broad suite still has non-package residual failures after V46
  lifecycle count fixes.
- Full `ruff check src tests`: run; fails on existing repo style findings.
- Full `mypy src`: run; fails on two existing `review_burden_mart.py` errors.
