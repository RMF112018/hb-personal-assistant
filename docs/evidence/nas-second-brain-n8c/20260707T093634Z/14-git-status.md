# 14 — Git Status (uncommitted; stop-before-commit)

Branch `ops/nas-second-brain-n8c-12-source-root-connector-20260707T091206Z`, base `0e2876c7` (N8C-11). HEAD
still at base — **all N8C-12 work is uncommitted**. No push, no PR, no merge.

## Modified (6 tracked; +353 / −0)
```
 M src/hb_assistant/cli/main.py                          (register source-connector group)
 M src/hb_assistant/construction/analytics/api.py        (6 read-only GET routes; /search before /{id})
 M src/hb_assistant/nas_mcp/broker.py                    (6 RO tools tuple + dispatch + _invoke)
 M src/hb_assistant/nas_mcp/profile.py                   (kill switch + gate_status)
 M src/hb_assistant/nas_mcp/tool_registration.py         (register 6 read tools + descriptions)
 M src/hb_assistant/obsidian_mcp/source_index_repository.py (3 additive root-aware/keyset read methods)
```
**`store/migrator.py` is NOT modified** → schema stays 107 (no-schema-bump proof). No schema head tests
modified.

## New (4 untracked source + 4 test + 1 evidence dir)
```
?? src/hb_assistant/obsidian_mcp/source_connector_models.py    (source_ref + cursor codecs, mime, shaping)
?? src/hb_assistant/obsidian_mcp/source_content_provider.py    (narrow bounded single-file reader)
?? src/hb_assistant/obsidian_mcp/source_connector_service.py   (read service behind CLI/API/MCP)
?? src/hb_assistant/cli/source_connector.py                    (source-connector CLI group)
?? tests/test_source_connector_service.py
?? tests/test_fastapi_analytics_source_connector.py
?? tests/test_nas_mcp_source_connector.py
?? tests/test_source_connector_eval.py
?? docs/evidence/nas-second-brain-n8c/20260707T093634Z/
```

No `agent_bridge` / `second_brain` / `construction/email` / source-card-render / scratch / recovery /
local-sensitive content in the change. `local-sensitive/` git-ignored (`.gitignore:205,209`;
`git check-ignore` confirmed on the evidence bundle's `local-sensitive/`).
