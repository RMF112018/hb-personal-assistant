# 13 — Git status (N8C-15, uncommitted)

Branch: `ops/nas-second-brain-n8c-15-workflow-contract-routing-20260707T113906Z`
Base commit (N8C-14): `ae483f39`  ·  HEAD: `ae483f39` (N8C-15 uncommitted)

## `git status --short`
```
 M src/hb_assistant/cli/main.py
 M src/hb_assistant/construction/analytics/api.py
?? src/hb_assistant/cli/workflow.py
?? src/hb_assistant/obsidian_mcp/workflow_models.py
?? src/hb_assistant/obsidian_mcp/workflow_registry.py
?? src/hb_assistant/obsidian_mcp/workflow_router.py
?? tests/test_cli_workflow.py
?? tests/test_fastapi_analytics_workflows.py
?? tests/test_workflow_models.py
?? tests/test_workflow_registry.py
?? tests/test_workflow_router.py
```

## `git diff --stat` (tracked modifications)
```
 src/hb_assistant/cli/main.py                   |  2 ++
 src/hb_assistant/construction/analytics/api.py | 45 ++++++++++++++++++++++++++
 2 files changed, 47 insertions(+)
```

## Scope invariants
- `store/migrator.py` NOT modified (schema stays V108).
- `nas_mcp/{broker,profile,tool_registration}.py` NOT modified (no MCP tools added).
- No `agent_bridge/`, `construction/second_brain/`, `construction/email/`, or source/card
  rendering file modified.
- New source: workflow_models.py, workflow_registry.py, workflow_router.py, cli/workflow.py.
- New tests: test_workflow_models/registry/router.py, test_cli_workflow.py,
  test_fastapi_analytics_workflows.py.
- Modified: cli/main.py (+2 registration lines), construction/analytics/api.py (+45, GET routes).
