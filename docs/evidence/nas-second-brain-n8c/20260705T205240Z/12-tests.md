# 12 — Tests & Verification

Run with `PYTHONPATH=src:subrepos/construction-financial-review/src <repo>/.venv/bin/python -m pytest`
(these source-intelligence / nas_mcp / fastapi tests are not in the fast bundles → direct targets).

## New tests — 44 total, all pass
| File | Tests | Focus |
|---|---|---|
| `tests/test_obsidian_source_navigation.py` | 18 | shared service: search/detail/linkage/ambiguity/state/stale/duplicate/ambiguous/recent/related; complete vault-note; traversal/absolute/NUL/hidden/**symlink-escape** rejection; relative-path assertions; RO conn threading |
| `tests/test_fastapi_analytics_assistant_nav.py` | 8 | API: shapes+guardrails, all-roles, `_assert_safe`, 404, 400 traversal, **GET-only route-shape** |
| `tests/test_nas_mcp_assistant_nav.py` | 12 | MCP: real content over RO snapshot, `query_only` write-block, denied tools, safe-mode, kill switch, count==56, registration ±flag, `hb_mcp_status` |
| `frontend/src/lib/assistantApi.test.ts` + `frontend/src/pages/AssistantPage.test.tsx` | 6 | client URL/method/header; read-only page render |

## Regression sweep — all green
`test_obsidian_source_card_identity` (N8C-2, 20), `test_nas_mcp_ai_outputs` /
`test_nas_mcp_remote_profile` / `test_obsidian_source_card_local_summary_marker` (N8C-1),
`test_nas_mcp_files_rw` (tool count 56), `test_source_index_repository`,
`test_fastapi_analytics_sources_status` → **98 passed** together with the new files.

## Lint & invariants
- `ruff check` clean on all new/changed files (`source_navigation.py`, `source_index_repository.py`,
  `broker.py`, `profile.py`, `tool_registration.py`, and the 3 new test files). `api.py` is in the
  ruff `extend-exclude` set; its pre-existing error count is unchanged (48 → 48; none in the added
  region).
- `LATEST_SCHEMA_VERSION` = 99 (no migration). `source_notes.py` untouched (card rendering
  byte-unchanged). `list_nas_obsidian_tool_names()` == 56 (unchanged); `assistant_*` adds 12 tools.
