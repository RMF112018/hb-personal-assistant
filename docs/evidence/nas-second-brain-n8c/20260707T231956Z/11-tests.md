# N8C-21 — tests

Run with `PYTHONPATH=src:subrepos/construction-financial-review/src`. Exit-0 + zero FAILED/ERROR is
authoritative (the env strips the summary line).

## New N8C-21 validation tests (green)
- `tests/test_n8c_final_validation.py` (6) — fresh DB→head 111, idempotent, ALL N8C tables present, assistant
  floor ≥48, every V100..V111 recorded, prior rows survive.
- `tests/test_n8c_mcp_tool_inventory_final.py` (8) — 13 groups, 78 tools by name, each independently gated,
  finality guard across all 78, denied raw tools, ai_outputs sole write, status advertises every group.

## Regression (green, exit 0) — 79 tests in the combined proof run
- `test_schema_version_head_consistency.py`, `test_nas_mcp_workflows.py`, `test_nas_mcp_quality.py`,
  `test_nas_mcp_action_stages.py`, `test_nas_mcp_feedback.py`.

## Local read-only smoke (green)
- `scripts/n8c-mcp-smoke.sh` → PASS (see `05b-smoke-output.txt`). `bash -n` clean.

## Cross-domain bundles
N8C-21 changes ZERO `src/hb_assistant/**` runtime code (only tests, a script, `validate-db.sh` constants, and a
doc), so `scripts/test-schedule.sh` (**345 passed**) and `scripts/test-forecasting.sh` (**1166 passed**),
validated under N8C-20 at the identical schema head V111 (`../20260707T225036Z/09b`,`/09c`), remain valid. No
re-run was required because no runtime code changed.

## Lint
`ruff check` clean on both new test files. `validate-db.sh` and `n8c-mcp-smoke.sh` pass `bash -n`.
