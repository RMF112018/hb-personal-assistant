# 11 — Tests

All runs use the shared venv:
`PYTHONPATH=src:subrepos/construction-financial-review/src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/python -m pytest`

## N8C-15 focused (54 tests, all pass)
`tests/test_workflow_models.py tests/test_workflow_registry.py tests/test_workflow_router.py
tests/test_cli_workflow.py tests/test_fastapi_analytics_workflows.py` → **54 passed** (confirmed twice:
prior session and again this session).

## Full N8C-1 → N8C-15 regression subset (68 files, 614 test functions)
Run in three batches (A: N8C-15/14/12/11 + schema-head; B: N8C-10/9/8/7; C: N8C-6/5/4/3/2/1), each
**exit code 0**. pytest returns 0 only when every collected test passes, so all 614+ tests passed. The
N8C-12 MCP finality guard (`tests/test_nas_mcp_source_connector.py`) is included in batch A and passed.
(Note: this environment drops pytest's textual summary line from captured background output; the exit code
is the authoritative pass/fail signal and was 0 for every batch, corroborated by a grep showing zero
`FAILED`/`ERROR` lines across all batch outputs.)

## Schedule canary
`scripts/test-schedule.sh` → **exit code 0** (schedule domain + migrator cross-domain guard green).

## Ruff
`ruff check` on all changed N8C-15 files (`obsidian_mcp/workflow_{models,registry,router}.py`,
`cli/workflow.py`, `cli/main.py`, 5 test files) → **All checks passed!**
`construction/analytics/api.py` → 48 pre-existing errors, **0 in the N8C-15 workflows GET block**
(legacy debt unchanged).

## Schema invariance
`LATEST_SCHEMA_VERSION == 108`; `git diff` shows `store/migrator.py` and `nas_mcp/*` unchanged on this
branch.

## Out of scope
`tests/test_review_router.py` (unrelated construction/email wall-clock date flake) was NOT run or modified.
