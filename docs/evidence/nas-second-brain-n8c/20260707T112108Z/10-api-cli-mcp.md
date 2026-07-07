# 10 — API / CLI / MCP Exposure

**CLI** (`hb-assistant answer-draft`, `cli/answer_draft.py`): `preview` / `build --dry-run|--apply` / `list` /
`export`, all `--json`. `--apply` is the sole writer (draft tables only). No final-answer/send/action/bridge
command. Registered in `cli/main.py`.

**API** (`construction/analytics/api.py`, all GET, all roles, read-only): `/api/assistant/answer-drafts`,
`/api/assistant/answer-drafts/summary` (declared BEFORE `/{draft_id}`), `/answer-drafts/{draft_id}` (404
`draft_not_found`), `/{draft_id}/sections`, `/{draft_id}/citations`, `/{draft_id}/export`. No
POST/PUT/PATCH/DELETE, no build route. `api.py` legacy ruff debt unchanged (48; 0 new in the draft block).

**MCP** (`nas_mcp/`, read-only over `mode=ro&immutable=1` + `PRAGMA query_only=ON`): gate
`assistant_answer_drafts_enabled()` (env `HB_MCP_ASSISTANT_ANSWER_DRAFTS`, default-ON, in `gate_status()`).
6 read tools: `assistant_list_drafts`, `assistant_get_draft`, `assistant_get_draft_sections`,
`assistant_get_draft_citations`, `assistant_get_draft_export`, `assistant_get_draft_summary`. **Tool
descriptions state they retrieve citation-safe draft artifacts only and generate no final answer / execute no
action** (clarification #9). Tool names use `draft` (not `answer`) so the remote surface carries no
answer-generation verb — satisfying the N8C-12 finality guard. New assistant remote tool total = **54**
(48 + 6); `ai_outputs_card_upsert` stays the only sanctioned remote write. No build/apply/answer/send/action
tool is registered.
