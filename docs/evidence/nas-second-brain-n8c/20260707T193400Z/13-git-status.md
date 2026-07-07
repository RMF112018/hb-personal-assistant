# 13 — Git Status (at close, UNCOMMITTED)

- Branch: `ops/nas-second-brain-n8c-17-core-workflows-20260707T185750Z`
- Base / HEAD: `65ee1268` (N8C-16, `feat(nas): add n8c workflow mcp tools`) — N8C-17 is UNCOMMITTED.
- Schema head: `LATEST_SCHEMA_VERSION = 108` (unchanged). `store/migrator.py` NOT in the diff.

## Working tree
```
 M src/hb_assistant/nas_mcp/broker.py                     # one authorized additive read-only line
 M src/hb_assistant/obsidian_mcp/workflow_models.py       # additive request fields + caps + policy const
 M src/hb_assistant/obsidian_mcp/workflow_registry.py     # 4 specs implemented; catalog notes
 M src/hb_assistant/obsidian_mcp/workflow_router.py       # delegate + list accessors + envelope fields
 M tests/test_nas_mcp_workflows.py                        # +workflow_sections assertions
 M tests/test_workflow_registry.py                        # implemented-not-deferred assertions
 M tests/test_workflow_router.py                          # implemented-behavior + handler AST guard
?? docs/evidence/nas-second-brain-n8c/20260707T193400Z/  # this bundle
?? src/hb_assistant/obsidian_mcp/workflow_handlers.py    # NEW: the four handlers
?? tests/test_workflow_handlers.py                        # NEW: 21 functions / 48 cases
```

No `store/migrator.py`, no schema-head test, no `agent_bridge/`, no `construction/second_brain|email/`, no
source/card rendering, no CLI/API route files touched. `local-sensitive/` is git-ignored via
`docs/evidence/**/local-sensitive/`.

## Commit posture
Stop before committing N8C-17 (per authorization). No push / PR / merge without Bobby's explicit
authorization. Commit message, when authorized, must be plain and carry **no AI trailer**.
