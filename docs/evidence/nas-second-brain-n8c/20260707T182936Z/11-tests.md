# 11 — Tests

Shared venv: `PYTHONPATH=src:subrepos/construction-financial-review/src
/Users/bobbyfetting/hb-personal-assistant/.venv/bin/python -m pytest`.

## N8C-16 focused (new)
`tests/test_nas_mcp_workflows.py` → **20 tests, all pass** (exit 0). Covers: schema-unchanged (V108) + no
workflow-persistence table in migrator; kill-switch on/off registration + dispatch; +6 set-difference tool
delta; no forbidden-substring names; existing finality guards still pass with workflow tools registered;
each tool bounded/read-only; RO snapshot write raises OperationalError; AST-scoped handler+views call no
writer/scan/source-read; inputs clamped; no workflow-persistence table created at runtime; safe-mode reads
work while `ai_outputs_card_upsert` write denied.

## Full N8C-1 → N8C-16 regression subset (69 files)
Run in batches, each **exit 0** (pytest exits 0 only when every collected test passes; corroborated by zero
`FAILED`/`ERROR` lines in all batch outputs):
- Batch A' (N8C-16 + N8C-15/14/12/11 + schema-head), Batch BC' (N8C-10 … N8C-1). Includes the N8C-12 +
  N8C-14 MCP finality guards, which pass with the six new workflow tools registered.

### One N8C-15 test updated (necessary, expected)
`tests/test_workflow_router.py::test_no_mcp_workflow_tools_added` asserted "nas_mcp has no `workflow`
reference" — correct at N8C-15 (which added no MCP), but N8C-16 INTENTIONALLY adds those MCP tools. It was
replaced by `test_router_library_stays_mcp_agnostic`, which asserts the router/models/registry LIBRARY adds
no MCP surface itself (no `register_nas_mcp_tools`/`fastmcp`/`@mcp.tool`/`nas_mcp` import) — the MCP wrapping
lives in `nas_mcp`, calling the router. Updated test passes.

## Schedule canary
`scripts/test-schedule.sh` → **exit 0**.

## Ruff
`ruff check` on `nas_mcp/{profile,broker,tool_registration}.py`, `tests/test_nas_mcp_workflows.py`, and the
updated `tests/test_workflow_router.py` → **All checks passed!**

## Schema invariance
`LATEST_SCHEMA_VERSION == 108`; `git diff` shows `store/migrator.py` unchanged (N8C-16 is MCP-only).

## Out of scope
`tests/test_review_router.py` (unrelated construction/email date flake) NOT run or modified.
