# N8C-16 — ChatGPT / MCP Live Workflow Consumption — Closeout

**Phase:** N8C-16 (live remote MCP consumption of the N8C-15 workflow router)
**Status:** implemented + verified; **UNCOMMITTED** (stop-before-commit per authorization)

## Commit lineage
- N8C-14 citation-safe drafts: `ae483f39`
- N8C-15 workflow routing (committed this session): `a5441dab`
- N8C-16 branch: `ops/nas-second-brain-n8c-16-live-workflow-mcp-20260707T182010Z`
- N8C-16 base commit: `a5441dab`  ·  HEAD at close: still `a5441dab` (N8C-16 uncommitted)

## What N8C-16 delivers
Six bounded, read-only remote MCP tools that expose the N8C-15 deterministic workflow router to live
LLM/MCP clients — served from a read-only DB snapshot, kill-switch gated, adding no schema, no
persistence, no build/apply, no execution, no final answers, no live source reads.

- `assistant_list_workflows` — the N8C-15 registry catalog (no DB).
- `assistant_route_workflow` — route a bounded request → normalized envelope.
- `assistant_get_workflow_context` — bounded context slice (artifacts + citations + labels + policy).
- `assistant_get_workflow_artifacts` — selected artifact REFERENCES (ids/kinds/status/metadata), not payloads.
- `assistant_get_workflow_policy` — the fixed no-execution policy block + request echo.
- `assistant_get_workflow_summary` — bounded, NON-FINAL route-metadata summary.

## Changed files (MCP-only)
- `src/hb_assistant/nas_mcp/profile.py` — `assistant_workflows_enabled()` kill-switch
  (`HB_MCP_ASSISTANT_WORKFLOWS`, default-ON) + `gate_status()` entry.
- `src/hb_assistant/nas_mcp/broker.py` — `ASSISTANT_WORKFLOW_TOOLS` tuple, 4 projection-view helpers,
  dispatch branch, `_invoke_assistant_workflows` handler (RO snapshot + `query_only=ON`), status advert.
- `src/hb_assistant/nas_mcp/tool_registration.py` — 6 `@mcp.tool()` registrations with read-only /
  no-execution / no-final-answer disclaimer docstrings.
- `tests/test_nas_mcp_workflows.py` — new (20 tests).
- `tests/test_workflow_router.py` — the now-superseded N8C-15 "no MCP workflow tools" guard replaced by a
  router-library-stays-MCP-agnostic guard (N8C-16 legitimately adds the MCP tools that test forbade).

## Deferred (unchanged)
N8C-13 operator UI (no branch). N8C-17 full workflow implementations. N8C-18 action staging.
N8D `agent_bridge` — untouched, not imported.
