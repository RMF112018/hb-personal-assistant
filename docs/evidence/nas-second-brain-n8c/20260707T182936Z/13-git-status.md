# 13 — Git status (N8C-16, uncommitted)

Branch: `ops/nas-second-brain-n8c-16-live-workflow-mcp-20260707T182010Z`
Base commit (N8C-15): `a5441dab`  ·  HEAD: `a5441dab` (N8C-16 uncommitted)

## `git status --short`
```
 M src/hb_assistant/nas_mcp/broker.py
 M src/hb_assistant/nas_mcp/profile.py
 M src/hb_assistant/nas_mcp/tool_registration.py
 M tests/test_workflow_router.py
?? tests/test_nas_mcp_workflows.py
```

## `git diff --stat`
```
 src/hb_assistant/nas_mcp/broker.py            | 110 +++++++++++++++++++++++++
 src/hb_assistant/nas_mcp/profile.py           |  16 ++++
 src/hb_assistant/nas_mcp/tool_registration.py | 113 ++++++++++++++++++++++++++
 tests/test_workflow_router.py                 |  11 ++-
 4 files changed, 246 insertions(+), 4 deletions(-)
```

## Changed files
- `nas_mcp/profile.py` — workflow kill-switch + gate_status entry.
- `nas_mcp/broker.py` — workflow tool tuple + 4 view helpers + dispatch branch + RO-snapshot handler + status advert.
- `nas_mcp/tool_registration.py` — 6 read-only `@mcp.tool()` registrations.
- `tests/test_nas_mcp_workflows.py` — NEW (20 tests).
- `tests/test_workflow_router.py` — updated the now-superseded N8C-15 "no MCP" guard to a
  router-library-stays-MCP-agnostic guard (N8C-16 legitimately adds the MCP tools it forbade).

## Scope invariants
- `store/migrator.py` NOT modified (schema stays V108).
- `obsidian_mcp/workflow_*.py`, `cli/`, `construction/analytics/api.py` NOT modified (N8C-15 source frozen).
- No `agent_bridge/`, `construction/second_brain/`, `construction/email/`, or source/card rendering change.
